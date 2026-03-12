"""Sensor entities for 3D Printer Maintenance integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COMPONENTS,
    CONF_PRINTER_NAME,
    DOMAIN,
    STATUS_DUE,
    STATUS_OK,
    STATUS_OVERDUE,
    STATUS_SOON,
)
from .coordinator import PrinterMaintenanceCoordinator

_LOGGER = logging.getLogger(__name__)

# Status → icon mapping
STATUS_ICON = {
    STATUS_OK: "mdi:check-circle",
    STATUS_SOON: "mdi:alert-circle-outline",
    STATUS_DUE: "mdi:alert",
    STATUS_OVERDUE: "mdi:close-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrinterMaintenanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    printer_name = entry.data.get(CONF_PRINTER_NAME, "Printer")
    unique_prefix = entry.entry_id

    entities: list[SensorEntity] = [
        TotalPrintHoursSensor(coordinator, printer_name, unique_prefix),
        TotalFilamentSensor(coordinator, printer_name, unique_prefix),
        TotalJobsSensor(coordinator, printer_name, unique_prefix),
    ]

    for comp_id, comp_info in COMPONENTS.items():
        entities += [
            ComponentHoursUsedSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
            ComponentHoursRemainingSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
            ComponentStatusSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
        ]

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class _BaseMaintenanceSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: PrinterMaintenanceCoordinator,
        printer_name: str,
        unique_prefix: str,
    ) -> None:
        self._coordinator = coordinator
        self._printer_name = printer_name
        self._unique_prefix = unique_prefix

    async def async_added_to_hass(self) -> None:
        self._coordinator.listeners.append(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._handle_update in self._coordinator.listeners:
            self._coordinator.listeners.remove(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Global stats sensors
# ---------------------------------------------------------------------------


class TotalPrintHoursSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = None

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_print_hours"
        self._attr_name = "Total Print Hours"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": printer_name,
            "manufacturer": "Printer Maintenance",
        }

    @property
    def native_value(self) -> float:
        return round(self._coordinator.total_print_hours, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "total_print_days": round(self._coordinator.total_print_hours / 24, 2),
        }


class TotalFilamentSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:spool"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = None

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_filament"
        self._attr_name = "Total Filament Used"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": printer_name,
        }

    @property
    def native_value(self) -> float:
        return round(self._coordinator.total_filament_m, 1)


class TotalJobsSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = None

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_jobs"
        self._attr_name = "Total Print Jobs"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": printer_name,
        }

    @property
    def native_value(self) -> int:
        return self._coordinator.total_jobs


# ---------------------------------------------------------------------------
# Per-component sensors
# ---------------------------------------------------------------------------


class _BaseComponentSensor(_BaseMaintenanceSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PrinterMaintenanceCoordinator,
        printer_name: str,
        unique_prefix: str,
        comp_id: str,
        comp_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._comp_id = comp_id
        self._comp_info = comp_info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": printer_name,
        }

    def _comp_data(self) -> dict[str, Any]:
        return self._coordinator.get_component_data(self._comp_id)


class ComponentHoursUsedSensor(_BaseComponentSensor):
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, printer_name, unique_prefix, comp_id, comp_info):
        super().__init__(coordinator, printer_name, unique_prefix, comp_id, comp_info)
        self._attr_unique_id = f"{unique_prefix}_{comp_id}_hours_used"
        self._attr_name = f"{comp_info['name']} Hours Used"
        self._attr_icon = comp_info["icon"]

    @property
    def native_value(self) -> float:
        return self._comp_data()["hours_used"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._comp_data()
        return {
            "interval_hours": d["interval_hours"],
            "last_reset": d["last_reset"],
        }


class ComponentHoursRemainingSensor(_BaseComponentSensor):
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, printer_name, unique_prefix, comp_id, comp_info):
        super().__init__(coordinator, printer_name, unique_prefix, comp_id, comp_info)
        self._attr_unique_id = f"{unique_prefix}_{comp_id}_hours_remaining"
        self._attr_name = f"{comp_info['name']} Hours Remaining"
        self._attr_icon = "mdi:timer-outline"

    @property
    def native_value(self) -> float:
        return self._comp_data()["hours_remaining"]


class ComponentStatusSensor(_BaseComponentSensor):

    def __init__(self, coordinator, printer_name, unique_prefix, comp_id, comp_info):
        super().__init__(coordinator, printer_name, unique_prefix, comp_id, comp_info)
        self._attr_unique_id = f"{unique_prefix}_{comp_id}_status"
        self._attr_name = f"{comp_info['name']} Status"

    @property
    def native_value(self) -> str:
        return self._comp_data()["status"]

    @property
    def icon(self) -> str:
        return STATUS_ICON.get(self._comp_data()["status"], "mdi:help-circle")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._comp_data()
        return {
            "hours_used": d["hours_used"],
            "hours_remaining": d["hours_remaining"],
            "interval_hours": d["interval_hours"],
            "last_reset": d["last_reset"],
        }
