"""Button entities to reset component maintenance counters."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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

    buttons = []
    for comp_id, comp_info in COMPONENTS.items():
        buttons.append(ResetComponentButton(coordinator, printer_name, unique_prefix, comp_id, comp_info))
        if comp_info.get("default_greasing_interval") is not None:
            buttons.append(GreaseComponentButton(coordinator, printer_name, unique_prefix, comp_id, comp_info))

    # Existing plates
    for plate_id, plate_info in coordinator.get_all_plates().items():
        buttons += make_plate_buttons(coordinator, printer_name, unique_prefix, plate_id, plate_info.get("name", plate_id))

    # Existing spools
    for spool_id, spool_info in coordinator.get_all_spools().items():
        buttons += make_spool_buttons(coordinator, printer_name, unique_prefix, spool_id, spool_info.get("name", spool_id))

    async_add_entities(buttons)

    # Store callbacks for dynamic registration
    coordinator._plate_button_add_fn = async_add_entities
    coordinator._spool_button_add_fn = async_add_entities


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_prefix)},
            name=printer_name,
            manufacturer="Printer Maintenance",
        )

    async def async_press(self) -> None:
        await self._coordinator.async_reset_component(self._comp_id)


class GreaseComponentButton(ButtonEntity):
    """Button that records a greasing event for a component."""

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
        self._attr_unique_id = f"{unique_prefix}_grease_{comp_id}"
        self._attr_name = f"Grease {comp_info['name']}"
        self._attr_icon = "mdi:oil"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_prefix)},
            name=printer_name,
            manufacturer="Printer Maintenance",
        )

    async def async_press(self) -> None:
        await self._coordinator.async_grease_component(self._comp_id)


class PlateResetButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id, plate_name):
        self._coordinator = coordinator
        self._plate_id = plate_id
        self._attr_unique_id = f"{unique_prefix}_reset_plate_{plate_id}"
        self._attr_name = f"Reset Plate {plate_name}"
        self._attr_icon = "mdi:restore"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_prefix)},
            name=printer_name,
            manufacturer="Printer Maintenance",
        )

    async def async_press(self):
        await self._coordinator.async_reset_plate(self._plate_id)


class PlateActivateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id, plate_name):
        self._coordinator = coordinator
        self._plate_id = plate_id
        self._attr_unique_id = f"{unique_prefix}_activate_plate_{plate_id}"
        self._attr_name = f"Activate Plate {plate_name}"
        self._attr_icon = "mdi:layers-plus"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_prefix)},
            name=printer_name,
            manufacturer="Printer Maintenance",
        )

    async def async_press(self):
        await self._coordinator.async_set_active_plate(self._plate_id)


class SpoolActivateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, printer_name, unique_prefix, spool_id, spool_name):
        self._coordinator = coordinator
        self._spool_id = spool_id
        self._attr_unique_id = f"{unique_prefix}_activate_spool_{spool_id}"
        self._attr_name = f"Activate Spool {spool_name}"
        self._attr_icon = "mdi:spool"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_prefix)},
            name=printer_name,
            manufacturer="Printer Maintenance",
        )

    async def async_press(self):
        await self._coordinator.async_set_active_spool(self._spool_id)


def make_plate_buttons(coordinator, printer_name, unique_prefix, plate_id, plate_name):
    return [
        PlateResetButton(coordinator, printer_name, unique_prefix, plate_id, plate_name),
        PlateActivateButton(coordinator, printer_name, unique_prefix, plate_id, plate_name),
    ]


def make_spool_buttons(coordinator, printer_name, unique_prefix, spool_id, spool_name):
    return [
        SpoolActivateButton(coordinator, printer_name, unique_prefix, spool_id, spool_name),
    ]
