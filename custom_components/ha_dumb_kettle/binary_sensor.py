"""Binary sensor platform for Dumb Kettle – fires when a boil completes."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_BOIL_COMPLETE_DURATION, DEFAULT_BOIL_COMPLETE_DURATION
from .coordinator import KettleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the boil-complete binary sensor."""
    coordinator: KettleCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name: str = config_entry.data.get("name", "Kettle")
    async_add_entities([KettleBoilCompleteSensor(coordinator, config_entry, name)])


class KettleBoilCompleteSensor(BinarySensorEntity):
    """Binary sensor that is ON for a short window after the kettle finishes boiling.

    Use this as a trigger in automations (e.g., send a notification when the
    kettle is ready).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Boil Complete"
    _attr_icon = "mdi:kettle-steam"

    def __init__(
        self,
        coordinator: KettleCoordinator,
        config_entry: ConfigEntry,
        device_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_boil_complete"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=device_name,
            manufacturer="DIY",
            model="Dumb Kettle Monitor",
        )
        self._unsub = None

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

    @property
    def is_on(self) -> bool:
        """Return True while the boil-complete window is active."""
        return self._coordinator.boil_complete

    @property
    def extra_state_attributes(self) -> dict:
        duration = self._config_entry.options.get(
            CONF_BOIL_COMPLETE_DURATION,
            self._config_entry.data.get(
                CONF_BOIL_COMPLETE_DURATION, DEFAULT_BOIL_COMPLETE_DURATION
            ),
        )
        return {
            "notification_window_s": duration,
            "last_boil_duration_s": self._coordinator.last_boil_duration,
        }
