"""Event platform for Dumb Kettle – fires once each time a boil finishes."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_BOIL_COMPLETE
from .coordinator import KettleCoordinator
from .entity import KettleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the boil event entity."""
    coordinator: KettleCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name: str = config_entry.data.get("name", "Kettle")
    async_add_entities([KettleBoilEvent(coordinator, config_entry, name, "boil_event")])


class KettleBoilEvent(KettleEntity, EventEntity):
    """Fires a ``boil_complete`` event when the kettle finishes a boil.

    Trigger automations on this rather than the Boil Complete binary sensor:
    it fires exactly once per boil and carries the boil duration.
    """

    _attr_name = "Boil"
    _attr_icon = "mdi:kettle-steam"
    _attr_event_types = [EVENT_BOIL_COMPLETE]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.register_boil_callback(self._handle_boil)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Only boils change this entity, not every power reading."""

    @callback
    def _handle_boil(self, duration: float, boil_count: int) -> None:
        self._trigger_event(
            EVENT_BOIL_COMPLETE,
            {"duration_s": duration, "boil_count": boil_count},
        )
        self.async_write_ha_state()
