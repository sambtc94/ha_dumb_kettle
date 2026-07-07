"""Kettle state coordinator – tracks idle/boiling, boil timing, and boil-complete flag."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
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

        # Latest power reading from the sensor
        self.current_power: float | None = None

        # Timing
        self._boil_start: datetime | None = None
        self.last_boil_duration: float | None = None  # seconds
        self.boil_count: int = 0

        # Boil-complete flag
        self.boil_complete: bool = False
        self._boil_complete_unsub: Callable | None = None

        # Listeners that want to be notified of state changes
        self._update_callbacks: list[Callable] = []

        # Internal tracking to debounce threshold crossings
        self._power_above_threshold: bool = False

        # Cleanup holder
        self._unsub_power: Callable | None = None

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
        state = self.hass.states.get(power_sensor)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self.current_power = float(state.state)
                self._evaluate_power(self.current_power)
            except (ValueError, TypeError):
                pass

    async def async_unload(self) -> None:
        """Cancel subscriptions."""
        if self._unsub_power:
            self._unsub_power()
            self._unsub_power = None
        if self._boil_complete_unsub:
            self._boil_complete_unsub()
            self._boil_complete_unsub = None

    # ------------------------------------------------------------------
    # Entity callback registration
    # ------------------------------------------------------------------

    def register_update_callback(self, callback_fn: Callable) -> Callable:
        """Register a callback to be fired on every state change.

        Returns an unregister function.
        """
        self._update_callbacks.append(callback_fn)

        def _remove():
            self._update_callbacks.remove(callback_fn)

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
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        try:
            power = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Could not parse power value '%s' from %s",
                new_state.state,
                new_state.entity_id,
            )
            return
        self.current_power = power
        self._evaluate_power(power)

    def _evaluate_power(self, power: float) -> None:
        """Update kettle state based on the current power reading."""
        boiling_threshold: float = self._config_entry.options.get(
            CONF_BOILING_THRESHOLD,
            self._config_entry.data.get(CONF_BOILING_THRESHOLD, DEFAULT_BOILING_THRESHOLD),
        )
        idle_threshold: float = self._config_entry.options.get(
            CONF_IDLE_THRESHOLD,
            self._config_entry.data.get(CONF_IDLE_THRESHOLD, DEFAULT_IDLE_THRESHOLD),
        )

        if power >= boiling_threshold and self.kettle_state == STATE_IDLE:
            self._start_boil()
        elif power < idle_threshold and self.kettle_state == STATE_BOILING:
            self._end_boil()

    def _start_boil(self) -> None:
        """Transition to boiling state."""
        self.kettle_state = STATE_BOILING
        self._boil_start = dt_util.utcnow()
        _LOGGER.debug("Kettle started boiling at %s", self._boil_start)
        self._notify_listeners()

    def _end_boil(self) -> None:
        """Transition back to idle and record the boil duration."""
        min_duration: float = self._config_entry.options.get(
            CONF_MIN_BOIL_DURATION,
            self._config_entry.data.get(CONF_MIN_BOIL_DURATION, DEFAULT_MIN_BOIL_DURATION),
        )

        if self._boil_start is not None:
            duration = (dt_util.utcnow() - self._boil_start).total_seconds()
            if duration >= min_duration:
                self.last_boil_duration = round(duration, 1)
                self.boil_count += 1
                _LOGGER.debug(
                    "Kettle finished boiling – duration %.1f s (total boils: %d)",
                    self.last_boil_duration,
                    self.boil_count,
                )
                self._trigger_boil_complete()
            else:
                _LOGGER.debug(
                    "Boil ignored – duration %.1f s is below minimum %s s",
                    duration,
                    min_duration,
                )

        self.kettle_state = STATE_IDLE
        self._boil_start = None
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Boil-complete flag management
    # ------------------------------------------------------------------

    def _trigger_boil_complete(self) -> None:
        """Set boil_complete = True and schedule auto-reset."""
        # Cancel any pending reset timer
        if self._boil_complete_unsub:
            self._boil_complete_unsub()
            self._boil_complete_unsub = None

        self.boil_complete = True

        complete_duration: int = self._config_entry.options.get(
            CONF_BOIL_COMPLETE_DURATION,
            self._config_entry.data.get(
                CONF_BOIL_COMPLETE_DURATION, DEFAULT_BOIL_COMPLETE_DURATION
            ),
        )

        from homeassistant.helpers.event import async_call_later  # local import to avoid circular

        self._boil_complete_unsub = async_call_later(
            self.hass, timedelta(seconds=complete_duration), self._reset_boil_complete
        )

    @callback
    def _reset_boil_complete(self, _now) -> None:
        """Reset the boil-complete flag after the notification window."""
        self.boil_complete = False
        self._boil_complete_unsub = None
        _LOGGER.debug("Boil-complete flag reset")
        self._notify_listeners()
