"""Sensor platform for Dumb Kettle – state, last boil duration, boil count and power."""
from __future__ import annotations

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import ATTR_BOIL_STARTED, DOMAIN, STATE_BOILING
from .coordinator import KettleCoordinator
from .entity import KettleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: KettleCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name: str = config_entry.data.get("name", "Kettle")

    async_add_entities(
        [
            KettleStateSensor(coordinator, config_entry, name, "state"),
            KettleLastBoilDurationSensor(
                coordinator, config_entry, name, "last_boil_duration"
            ),
            KettleBoilCountSensor(coordinator, config_entry, name, "boil_count"),
            KettlePowerSensor(coordinator, config_entry, name, "power"),
        ]
    )


# ---------------------------------------------------------------------------
# Kettle state sensor  (idle / boiling)
# ---------------------------------------------------------------------------

class KettleStateSensor(KettleEntity, SensorEntity, RestoreEntity):
    """Sensor reporting the current kettle state."""

    _attr_name = "State"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # If HA restarted mid-boil, keep the original start time so the
        # recorded duration isn't cut short.
        last = await self.async_get_last_state()
        if last is not None and last.state == STATE_BOILING:
            started = dt_util.parse_datetime(
                str(last.attributes.get(ATTR_BOIL_STARTED, ""))
            )
            if started is not None:
                self._coordinator.restore_boil_start(dt_util.as_utc(started))

    @property
    def available(self) -> bool:
        return self._coordinator.available

    @property
    def native_value(self) -> str:
        return self._coordinator.kettle_state

    @property
    def icon(self) -> str:
        if self._coordinator.kettle_state == STATE_BOILING:
            return "mdi:kettle-steam"
        return "mdi:kettle"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self._coordinator.last_boil_duration is not None:
            attrs["last_boil_duration_s"] = self._coordinator.last_boil_duration
        attrs["boil_count"] = self._coordinator.boil_count
        if self._coordinator.boil_start is not None:
            attrs[ATTR_BOIL_STARTED] = self._coordinator.boil_start.isoformat()
        return attrs


# ---------------------------------------------------------------------------
# Last boil duration sensor
# ---------------------------------------------------------------------------

class KettleLastBoilDurationSensor(KettleEntity, RestoreSensor):
    """Duration of the most recent boil in seconds (survives restarts)."""

    _attr_name = "Last Boil Duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._coordinator.restore_totals(
                    last_boil_duration=float(last.native_value)
                )
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> float | None:
        return self._coordinator.last_boil_duration


# ---------------------------------------------------------------------------
# Boil count sensor
# ---------------------------------------------------------------------------

class KettleBoilCountSensor(KettleEntity, RestoreSensor):
    """Running total of boils (survives restarts and reloads)."""

    _attr_name = "Boil Count"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._coordinator.restore_totals(
                    boil_count=int(float(last.native_value))
                )
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> int:
        return self._coordinator.boil_count


# ---------------------------------------------------------------------------
# Power consumption sensor
# ---------------------------------------------------------------------------

class KettlePowerSensor(KettleEntity, SensorEntity):
    """Current power draw, mirrored from the source sensor."""

    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    @property
    def available(self) -> bool:
        return self._coordinator.available

    @property
    def native_value(self) -> float | None:
        return self._coordinator.current_power
