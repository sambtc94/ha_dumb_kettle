"""Shared base entity for Dumb Kettle."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import KettleCoordinator


class KettleEntity(Entity):
    """Base entity that follows coordinator updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: KettleCoordinator,
        config_entry: ConfigEntry,
        device_name: str,
        key: str,
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=device_name,
            manufacturer="DIY",
            model="Dumb Kettle Monitor",
        )

    async def async_added_to_hass(self) -> None:
        """Register update callback with coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.register_update_callback(
                self._handle_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
