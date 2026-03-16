"""3D Printer Maintenance — Home Assistant custom integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import COMPONENTS, DOMAIN, PLATFORMS
from .coordinator import PrinterMaintenanceCoordinator
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

# Service schemas
_ENTRY_ID_SCHEMA = vol.Optional("entry_id")

RESET_COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Required("component"): vol.In(list(COMPONENTS.keys())),
        _ENTRY_ID_SCHEMA: cv.string,
    }
)

SET_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Required("component"): vol.In(list(COMPONENTS.keys())),
        vol.Required("interval_hours"): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=10000)
        ),
        _ENTRY_ID_SCHEMA: cv.string,
    }
)

ADD_HOURS_SCHEMA = vol.Schema(
    {
        vol.Required("hours"): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
        vol.Optional("component"): vol.In(list(COMPONENTS.keys())),
        _ENTRY_ID_SCHEMA: cv.string,
    }
)

SET_TOTAL_HOURS_SCHEMA = vol.Schema(
    {
        vol.Required("hours"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        _ENTRY_ID_SCHEMA: cv.string,
    }
)

SET_TOTAL_FILAMENT_SCHEMA = vol.Schema(
    {
        vol.Required("meters"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        _ENTRY_ID_SCHEMA: cv.string,
    }
)

ADD_PLATE_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("interval_hours", default=200): vol.All(vol.Coerce(float), vol.Range(min=1, max=10000)),
    _ENTRY_ID_SCHEMA: cv.string,
})

REMOVE_PLATE_SCHEMA = vol.Schema({
    vol.Required("plate_id"): cv.string,
    _ENTRY_ID_SCHEMA: cv.string,
})

SET_ACTIVE_PLATE_SCHEMA = vol.Schema({
    vol.Required("plate_id"): cv.string,
    _ENTRY_ID_SCHEMA: cv.string,
})

RESET_PLATE_SCHEMA = vol.Schema({
    vol.Required("plate_id"): cv.string,
    _ENTRY_ID_SCHEMA: cv.string,
})

ADD_SPOOL_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("material", default="PLA"): cv.string,
    vol.Optional("brand", default=""): cv.string,
    vol.Optional("color", default=""): cv.string,
    vol.Optional("initial_weight_g", default=1000): vol.All(vol.Coerce(float), vol.Range(min=1, max=10000)),
    vol.Optional("diameter_mm", default=1.75): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=3.0)),
    _ENTRY_ID_SCHEMA: cv.string,
})

REMOVE_SPOOL_SCHEMA = vol.Schema({
    vol.Required("spool_id"): cv.string,
    _ENTRY_ID_SCHEMA: cv.string,
})

SET_ACTIVE_SPOOL_SCHEMA = vol.Schema({
    vol.Required("spool_id"): cv.string,
    _ENTRY_ID_SCHEMA: cv.string,
})

UPDATE_SPOOL_WEIGHT_SCHEMA = vol.Schema({
    vol.Required("spool_id"): cv.string,
    vol.Required("remaining_weight_g"): vol.All(vol.Coerce(float), vol.Range(min=0, max=10000)),
    _ENTRY_ID_SCHEMA: cv.string,
})

_GREASABLE_COMPONENTS = [c for c, info in COMPONENTS.items() if info.get("default_greasing_interval") is not None]

GREASE_COMPONENT_SCHEMA = vol.Schema({
    vol.Required("component"): vol.In(_GREASABLE_COMPONENTS),
    _ENTRY_ID_SCHEMA: cv.string,
})

SET_GREASING_INTERVAL_SCHEMA = vol.Schema({
    vol.Required("component"): vol.In(_GREASABLE_COMPONENTS),
    vol.Required("interval_hours"): vol.All(vol.Coerce(float), vol.Range(min=1, max=10000)),
    _ENTRY_ID_SCHEMA: cv.string,
})


def _get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> list[PrinterMaintenanceCoordinator]:
    """Return coordinator(s) targeted by a service call."""
    entry_id: str | None = call.data.get("entry_id")
    entries: dict[str, Any] = hass.data.get(DOMAIN, {})
    if entry_id:
        coord = entries.get(entry_id)
        return [coord] if coord else []
    return list(entries.values())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    coordinator = PrinterMaintenanceCoordinator(hass, entry)
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Register frontend card and services once (first entry only)
    if not hass.services.has_service(DOMAIN, "reset_component"):
        await async_register_frontend(hass)
        _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: PrinterMaintenanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_shutdown()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove services when no entries remain
    if not hass.data[DOMAIN]:
        for svc in (
            "reset_component", "set_interval", "add_hours", "set_total_hours", "set_total_filament",
            "add_plate", "remove_plate", "set_active_plate", "reset_plate",
            "add_spool", "remove_spool", "set_active_spool", "update_spool_weight",
            "grease_component", "set_greasing_interval",
        ):
            hass.services.async_remove(DOMAIN, svc)

    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services."""

    async def handle_reset_component(call: ServiceCall) -> None:
        component = call.data["component"]
        for coord in _get_coordinator(hass, call):
            await coord.async_reset_component(component)

    async def handle_set_interval(call: ServiceCall) -> None:
        component = call.data["component"]
        interval = call.data["interval_hours"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_interval(component, interval)

    async def handle_add_hours(call: ServiceCall) -> None:
        hours = call.data["hours"]
        component = call.data.get("component")
        for coord in _get_coordinator(hass, call):
            await coord.async_add_hours(hours, component)

    async def handle_set_total_hours(call: ServiceCall) -> None:
        hours = call.data["hours"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_total_hours(hours)

    async def handle_set_total_filament(call: ServiceCall) -> None:
        meters = call.data["meters"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_total_filament(meters)

    async def handle_add_plate(call: ServiceCall) -> None:
        name = call.data["name"]
        interval_hours = call.data["interval_hours"]
        for coord in _get_coordinator(hass, call):
            await coord.async_add_plate(name, interval_hours)

    async def handle_remove_plate(call: ServiceCall) -> None:
        plate_id = call.data["plate_id"]
        for coord in _get_coordinator(hass, call):
            await coord.async_remove_plate(plate_id)

    async def handle_set_active_plate(call: ServiceCall) -> None:
        plate_id = call.data["plate_id"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_active_plate(plate_id)

    async def handle_reset_plate(call: ServiceCall) -> None:
        plate_id = call.data["plate_id"]
        for coord in _get_coordinator(hass, call):
            await coord.async_reset_plate(plate_id)

    async def handle_add_spool(call: ServiceCall) -> None:
        for coord in _get_coordinator(hass, call):
            await coord.async_add_spool(
                name=call.data["name"],
                material=call.data["material"],
                brand=call.data["brand"],
                color=call.data["color"],
                initial_weight_g=call.data["initial_weight_g"],
                diameter_mm=call.data["diameter_mm"],
            )

    async def handle_remove_spool(call: ServiceCall) -> None:
        spool_id = call.data["spool_id"]
        for coord in _get_coordinator(hass, call):
            await coord.async_remove_spool(spool_id)

    async def handle_set_active_spool(call: ServiceCall) -> None:
        spool_id = call.data["spool_id"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_active_spool(spool_id)

    async def handle_update_spool_weight(call: ServiceCall) -> None:
        spool_id = call.data["spool_id"]
        remaining_weight_g = call.data["remaining_weight_g"]
        for coord in _get_coordinator(hass, call):
            await coord.async_update_spool_weight(spool_id, remaining_weight_g)

    async def handle_grease_component(call: ServiceCall) -> None:
        component = call.data["component"]
        for coord in _get_coordinator(hass, call):
            await coord.async_grease_component(component)

    async def handle_set_greasing_interval(call: ServiceCall) -> None:
        component = call.data["component"]
        interval = call.data["interval_hours"]
        for coord in _get_coordinator(hass, call):
            await coord.async_set_greasing_interval(component, interval)

    hass.services.async_register(
        DOMAIN, "reset_component", handle_reset_component, schema=RESET_COMPONENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_interval", handle_set_interval, schema=SET_INTERVAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_hours", handle_add_hours, schema=ADD_HOURS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_total_hours", handle_set_total_hours, schema=SET_TOTAL_HOURS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_total_filament", handle_set_total_filament, schema=SET_TOTAL_FILAMENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_plate", handle_add_plate, schema=ADD_PLATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "remove_plate", handle_remove_plate, schema=REMOVE_PLATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_active_plate", handle_set_active_plate, schema=SET_ACTIVE_PLATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "reset_plate", handle_reset_plate, schema=RESET_PLATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_spool", handle_add_spool, schema=ADD_SPOOL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "remove_spool", handle_remove_spool, schema=REMOVE_SPOOL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_active_spool", handle_set_active_spool, schema=SET_ACTIVE_SPOOL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "update_spool_weight", handle_update_spool_weight, schema=UPDATE_SPOOL_WEIGHT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "grease_component", handle_grease_component, schema=GREASE_COMPONENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_greasing_interval", handle_set_greasing_interval, schema=SET_GREASING_INTERVAL_SCHEMA
    )
