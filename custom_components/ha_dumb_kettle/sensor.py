"""Sensor platform for Dumb Kettle – state, last boil duration, and boil count."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATE_BOILING, STATE_IDLE
from .coordinator import KettleCoordinator

_LOGGER = logging.getLogger(__name__)


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
            KettleStateSensor(coordinator, config_entry, name),
            KettleLastBoilDurationSensor(coordinator, config_entry, name),
            KettleBoilCountSensor(coordinator, config_entry, name),
        ]
    )


# ---------------------------------------------------------------------------
# Base class shared by all Dumb Kettle sensors
# ---------------------------------------------------------------------------

class _KettleBaseSensor(SensorEntity):
    """Base sensor that subscribes to coordinator updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: KettleCoordinator,
        config_entry: ConfigEntry,
        device_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._device_name = device_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=device_name,
            manufacturer="DIY",
            model="Dumb Kettle Monitor",
        )
        self._unsub: Any = None

    async def async_added_to_hass(self) -> None:
        """Register update callback with coordinator."""
        self._unsub = self._coordinator.register_update_callback(
            self._handle_coordinator_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Kettle state sensor  (idle / boiling)
# ---------------------------------------------------------------------------

class KettleStateSensor(_KettleBaseSensor):
    """Sensor reporting the current kettle state."""

    _attr_icon = "mdi:kettle"
    _attr_name = "State"

    def __init__(self, coordinator, config_entry, device_name):
        super().__init__(coordinator, config_entry, device_name)
        self._attr_unique_id = f"{config_entry.entry_id}_state"

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
        return attrs


# ---------------------------------------------------------------------------
# Last boil duration sensor
# ---------------------------------------------------------------------------

class KettleLastBoilDurationSensor(_KettleBaseSensor):
    """Sensor reporting the duration of the most recent boil in seconds."""

    _attr_name = "Last Boil Duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, config_entry, device_name):
        super().__init__(coordinator, config_entry, device_name)
        self._attr_unique_id = f"{config_entry.entry_id}_last_boil_duration"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.last_boil_duration


# ---------------------------------------------------------------------------
# Boil count sensor
# ---------------------------------------------------------------------------

class KettleBoilCountSensor(_KettleBaseSensor):
    """Sensor counting how many times the kettle has boiled since the integration started."""

    _attr_name = "Boil Count"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, config_entry, device_name):
        super().__init__(coordinator, config_entry, device_name)
        self._attr_unique_id = f"{config_entry.entry_id}_boil_count"

    @property
    def native_value(self) -> int:
        return self._coordinator.boil_count
