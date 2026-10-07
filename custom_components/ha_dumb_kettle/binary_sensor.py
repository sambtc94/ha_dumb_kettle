"""Binary sensor platform for Dumb Kettle – fires when a boil completes."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KettleCoordinator
from .entity import KettleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the boil-complete binary sensor."""
    coordinator: KettleCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name: str = config_entry.data.get("name", "Kettle")
    async_add_entities(
        [KettleBoilCompleteSensor(coordinator, config_entry, name, "boil_complete")]
    )


class KettleBoilCompleteSensor(KettleEntity, BinarySensorEntity):
    """Binary sensor that is ON for a short window after the kettle finishes boiling.

    Use this as a trigger in automations (e.g., send a notification when the
    kettle is ready).
    """

    _attr_name = "Boil Complete"
    _attr_icon = "mdi:kettle-steam"

    @property
    def is_on(self) -> bool:
        """Return True while the boil-complete window is active."""
        return self._coordinator.boil_complete

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "notification_window_s": self._coordinator.boil_complete_duration,
            "last_boil_duration_s": self._coordinator.last_boil_duration,
        }
