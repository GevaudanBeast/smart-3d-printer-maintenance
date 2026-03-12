"""Button entities to reset component maintenance counters."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COMPONENTS, CONF_PRINTER_NAME, DOMAIN
from .coordinator import PrinterMaintenanceCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrinterMaintenanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    printer_name = entry.data.get(CONF_PRINTER_NAME, "Printer")
    unique_prefix = entry.entry_id

    async_add_entities(
        [
            ResetComponentButton(coordinator, printer_name, unique_prefix, comp_id, comp_info)
            for comp_id, comp_info in COMPONENTS.items()
        ]
    )


class ResetComponentButton(ButtonEntity):
    """Button that resets a component's maintenance counter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PrinterMaintenanceCoordinator,
        printer_name: str,
        unique_prefix: str,
        comp_id: str,
        comp_info: dict[str, Any],
    ) -> None:
        self._coordinator = coordinator
        self._comp_id = comp_id
        self._attr_unique_id = f"{unique_prefix}_reset_{comp_id}"
        self._attr_name = f"Reset {comp_info['name']}"
        self._attr_icon = "mdi:restore"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": printer_name,
        }

    async def async_press(self) -> None:
        await self._coordinator.async_reset_component(self._comp_id)
