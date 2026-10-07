"""Kettle state coordinator – tracks idle/boiling, boil timing, and boil-complete flag."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
import homeassistant.util.dt as dt_util

from .const import (
    CONF_BOIL_COMPLETE_DURATION,
    CONF_BOILING_THRESHOLD,
    CONF_IDLE_THRESHOLD,
    CONF_MIN_BOIL_DURATION,
    CONF_POWER_SENSOR,
    DEFAULT_BOIL_COMPLETE_DURATION,
    DEFAULT_BOILING_THRESHOLD,
    DEFAULT_IDLE_THRESHOLD,
    DEFAULT_MIN_BOIL_DURATION,
    MAX_RESTORED_BOIL_AGE,
    STATE_BOILING,
    STATE_IDLE,
)

_LOGGER = logging.getLogger(__name__)


class KettleCoordinator:
    """Centralised coordinator that derives kettle state from a power sensor."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        self.hass = hass
        self._config_entry = config_entry

        # Current logical state
        self.kettle_state: str = STATE_IDLE

        # Whether the source power sensor is currently reporting
        self.available: bool = False

        # Latest power reading from the sensor
        self.current_power: float | None = None

        # Timing
        self.boil_start: datetime | None = None
        self.last_boil_duration: float | None = None  # seconds
        self.boil_count: int = 0

        # True once a boil has finished since setup, so a late restore
        # never overwrites newer values
        self._boil_recorded_since_setup: bool = False

        # Boil-complete flag
        self.boil_complete: bool = False
        self._boil_complete_unsub: Callable | None = None

        # Listeners that want to be notified of state changes
        self._update_callbacks: list[Callable] = []

        # Listeners that want to know when a boil finishes (event entity)
        self._boil_callbacks: list[Callable[[float, int], None]] = []

        # Cleanup holder
        self._unsub_power: Callable | None = None

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _opt(self, key: str, default: float) -> float:
        """Return an option, falling back to the original setup data."""
        return float(
            self._config_entry.options.get(
                key, self._config_entry.data.get(key, default)
            )
        )

    @property
    def boil_complete_duration(self) -> float:
        return self._opt(CONF_BOIL_COMPLETE_DURATION, DEFAULT_BOIL_COMPLETE_DURATION)

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Start listening to the configured power sensor."""
        power_sensor = self._config_entry.data[CONF_POWER_SENSOR]
        self._unsub_power = async_track_state_change_event(
            self.hass, power_sensor, self._handle_power_change
        )
        # Initialise state from the current sensor value (if available)
        self._process_state(self.hass.states.get(power_sensor))

    async def async_unload(self) -> None:
        """Cancel subscriptions."""
        if self._unsub_power:
            self._unsub_power()
            self._unsub_power = None
        if self._boil_complete_unsub:
            self._boil_complete_unsub()
            self._boil_complete_unsub = None

    # ------------------------------------------------------------------
    # Restore (called by entities as they are added)
    # ------------------------------------------------------------------

    @callback
    def restore_totals(
        self, boil_count: int | None = None, last_boil_duration: float | None = None
    ) -> None:
        """Restore persisted totals after a restart or reload."""
        if self._boil_recorded_since_setup:
            return
        changed = False
        if boil_count is not None and boil_count > self.boil_count:
            self.boil_count = boil_count
            changed = True
        if last_boil_duration is not None and self.last_boil_duration is None:
            self.last_boil_duration = last_boil_duration
            changed = True
        if changed:
            self._notify_listeners()

    @callback
    def restore_boil_start(self, boil_start: datetime | None) -> None:
        """Keep the original start time if HA restarted mid-boil."""
        if (
            boil_start is None
            or self.kettle_state != STATE_BOILING
            or self.boil_start is None
        ):
            return
        age = dt_util.utcnow() - boil_start
        if timedelta(0) <= age <= MAX_RESTORED_BOIL_AGE and boil_start < self.boil_start:
            _LOGGER.debug("Restored boil start time %s", boil_start)
            self.boil_start = boil_start
            self._notify_listeners()

    # ------------------------------------------------------------------
    # Entity callback registration
    # ------------------------------------------------------------------

    def register_update_callback(self, callback_fn: Callable) -> Callable:
        """Register a callback to be fired on every state change.

        Returns an unregister function.
        """
        self._update_callbacks.append(callback_fn)

        def _remove():
            if callback_fn in self._update_callbacks:
                self._update_callbacks.remove(callback_fn)

        return _remove

    def register_boil_callback(self, callback_fn: Callable[[float, int], None]) -> Callable:
        """Register a callback fired once per completed boil (duration, count)."""
        self._boil_callbacks.append(callback_fn)

        def _remove():
            if callback_fn in self._boil_callbacks:
                self._boil_callbacks.remove(callback_fn)

        return _remove

    @callback
    def _notify_listeners(self) -> None:
        for cb in list(self._update_callbacks):
            cb()

    # ------------------------------------------------------------------
    # Power sensor event handler
    # ------------------------------------------------------------------

    @callback
    def _handle_power_change(self, event) -> None:
        """React to a state change on the power sensor entity."""
        self._process_state(event.data.get("new_state"))

    @callback
    def _process_state(self, new_state) -> None:
        """Handle a new source state, including unavailable/unknown."""
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._set_unavailable()
            return
        try:
            power = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Could not parse power value '%s' from %s",
                new_state.state,
                new_state.entity_id,
            )
            self._set_unavailable()
            return

        self.available = True
        if not self._evaluate_power(power):
            # No idle/boiling transition, but the power value (or
            # availability) changed, so the entities still need refreshing.
            self._notify_listeners()

    @callback
    def _set_unavailable(self) -> None:
        """Source stopped reporting: drop any boil in progress."""
        if not self.available and self.kettle_state == STATE_IDLE:
            return
        self.available = False
        self.current_power = None
        if self.kettle_state == STATE_BOILING:
            _LOGGER.debug("Power sensor unavailable mid-boil – boil discarded")
            self.kettle_state = STATE_IDLE
            self.boil_start = None
        self._notify_listeners()

    def _evaluate_power(self, power: float) -> bool:
        """Update kettle state from a power reading.

        Returns True if listeners were notified.
        """
        self.current_power = power
        boiling_threshold = self._opt(CONF_BOILING_THRESHOLD, DEFAULT_BOILING_THRESHOLD)
        idle_threshold = self._opt(CONF_IDLE_THRESHOLD, DEFAULT_IDLE_THRESHOLD)

        if power >= boiling_threshold and self.kettle_state == STATE_IDLE:
            self._start_boil()
            return True
        if power < idle_threshold and self.kettle_state == STATE_BOILING:
            self._end_boil()
            return True
        return False

    def _start_boil(self) -> None:
        """Transition to boiling state."""
        self.kettle_state = STATE_BOILING
        self.boil_start = dt_util.utcnow()
        _LOGGER.debug("Kettle started boiling at %s", self.boil_start)
        self._notify_listeners()

    def _end_boil(self) -> None:
        """Transition back to idle and record the boil duration."""
        min_duration = self._opt(CONF_MIN_BOIL_DURATION, DEFAULT_MIN_BOIL_DURATION)

        if self.boil_start is not None:
            duration = (dt_util.utcnow() - self.boil_start).total_seconds()
            if duration >= min_duration:
                self.last_boil_duration = round(duration, 1)
                self.boil_count += 1
                self._boil_recorded_since_setup = True
                _LOGGER.debug(
                    "Kettle finished boiling – duration %.1f s (total boils: %d)",
                    self.last_boil_duration,
                    self.boil_count,
                )
                self._trigger_boil_complete()
                for cb in list(self._boil_callbacks):
                    cb(self.last_boil_duration, self.boil_count)
            else:
                _LOGGER.debug(
                    "Boil ignored – duration %.1f s is below minimum %s s",
                    duration,
                    min_duration,
                )

        self.kettle_state = STATE_IDLE
        self.boil_start = None
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Boil-complete flag management
    # ------------------------------------------------------------------

    def _trigger_boil_complete(self) -> None:
        """Set boil_complete = True and schedule auto-reset."""
        if self._boil_complete_unsub:
            self._boil_complete_unsub()
            self._boil_complete_unsub = None

        self.boil_complete = True
        self._boil_complete_unsub = async_call_later(
            self.hass,
            timedelta(seconds=self.boil_complete_duration),
            self._reset_boil_complete,
        )

    @callback
    def _reset_boil_complete(self, _now) -> None:
        """Reset the boil-complete flag after the notification window."""
        self.boil_complete = False
        self._boil_complete_unsub = None
        _LOGGER.debug("Boil-complete flag reset")
        self._notify_listeners()
