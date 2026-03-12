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
        for svc in ("reset_component", "set_interval", "add_hours"):
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

    hass.services.async_register(
        DOMAIN, "reset_component", handle_reset_component, schema=RESET_COMPONENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_interval", handle_set_interval, schema=SET_INTERVAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_hours", handle_add_hours, schema=ADD_HOURS_SCHEMA
    )
