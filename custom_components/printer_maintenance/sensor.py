"""Sensor entities for 3D Printer Maintenance integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
        TotalJobsOkSensor(coordinator, printer_name, unique_prefix),
        TotalJobsKoSensor(coordinator, printer_name, unique_prefix),
    ]

    for comp_id, comp_info in COMPONENTS.items():
        entities += [
            ComponentHoursUsedSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
            ComponentHoursRemainingSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
            ComponentStatusSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
            ComponentLastResetSensor(coordinator, printer_name, unique_prefix, comp_id, comp_info),
        ]

    # Register active plate/spool global sensors
    entities.append(ActivePlateSensor(coordinator, printer_name, unique_prefix))
    entities.append(ActiveSpoolSensor(coordinator, printer_name, unique_prefix))

    # Register existing plates
    for plate_id in coordinator.get_all_plates():
        entities += make_plate_sensors(coordinator, printer_name, unique_prefix, plate_id)

    # Register existing spools
    for spool_id in coordinator.get_all_spools():
        entities += make_spool_sensors(coordinator, printer_name, unique_prefix, spool_id)

    async_add_entities(entities)

    # Store callbacks for dynamic entity registration
    coordinator._plate_sensor_add_fn = async_add_entities
    coordinator._spool_sensor_add_fn = async_add_entities


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


def _device_info(domain: str, unique_prefix: str, printer_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(domain, unique_prefix)},
        name=printer_name,
        manufacturer="Printer Maintenance",
    )


# ---------------------------------------------------------------------------
# Global stats sensors
# ---------------------------------------------------------------------------


class TotalPrintHoursSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_print_hours"
        self._attr_name = "Total Print Hours"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

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

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_filament"
        self._attr_name = "Total Filament Used"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.total_filament_m, 1)


class TotalJobsSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_jobs"
        self._attr_name = "Total Print Jobs"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

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
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

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
        return {"interval_hours": d["interval_hours"], "last_reset": d["last_reset"]}


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


class ComponentLastResetSensor(_BaseComponentSensor):
    """Sensor exposing the date of last maintenance/greasing for a component."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, printer_name, unique_prefix, comp_id, comp_info):
        super().__init__(coordinator, printer_name, unique_prefix, comp_id, comp_info)
        self._attr_unique_id = f"{unique_prefix}_{comp_id}_last_reset"
        self._attr_name = f"{comp_info['name']} Last Maintenance"

    @property
    def native_value(self):
        last_reset = self._comp_data()["last_reset"]
        if last_reset is None:
            return None
        return dt_util.parse_datetime(last_reset)


class TotalJobsOkSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:check-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_jobs_ok"
        self._attr_name = "Total Jobs OK"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    @property
    def native_value(self) -> int:
        return self._coordinator.total_jobs_ok


class TotalJobsKoSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:close-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PrinterMaintenanceCoordinator, printer_name: str, unique_prefix: str) -> None:
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_total_jobs_ko"
        self._attr_name = "Total Jobs Failed"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    @property
    def native_value(self) -> int:
        return self._coordinator.total_jobs_ko


# ── Plate sensors ────────────────────────────────────────────────────────────

class _BasePlateSensor(_BaseMaintenanceSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id):
        super().__init__(coordinator, printer_name, unique_prefix)
        self._plate_id = plate_id
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    def _plate(self):
        return self._coordinator.get_plate_data(self._plate_id)


class PlateHoursUsedSensor(_BasePlateSensor):
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id):
        super().__init__(coordinator, printer_name, unique_prefix, plate_id)
        self._attr_unique_id = f"{unique_prefix}_plate_{plate_id}_hours_used"
        self._attr_name = f"Plate {self._coordinator.get_plate_data(plate_id)['name']} Hours Used"
        self._attr_icon = "mdi:layers-outline"

    @property
    def native_value(self):
        return self._plate()["hours_used"]

    @property
    def extra_state_attributes(self):
        d = self._plate()
        return {"name": d["name"], "interval_hours": d["interval_hours"], "last_reset": d["last_reset"], "active": d["active"]}


class PlateHoursRemainingSensor(_BasePlateSensor):
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id):
        super().__init__(coordinator, printer_name, unique_prefix, plate_id)
        self._attr_unique_id = f"{unique_prefix}_plate_{plate_id}_hours_remaining"
        self._attr_name = f"Plate {self._coordinator.get_plate_data(plate_id)['name']} Hours Remaining"
        self._attr_icon = "mdi:timer-outline"

    @property
    def native_value(self):
        return self._plate()["hours_remaining"]


class PlateStatusSensor(_BasePlateSensor):

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id):
        super().__init__(coordinator, printer_name, unique_prefix, plate_id)
        self._attr_unique_id = f"{unique_prefix}_plate_{plate_id}_status"
        self._attr_name = f"Plate {self._coordinator.get_plate_data(plate_id)['name']} Status"

    @property
    def native_value(self):
        return self._plate()["status"]

    @property
    def icon(self):
        return STATUS_ICON.get(self._plate()["status"], "mdi:help-circle")

    @property
    def extra_state_attributes(self):
        d = self._plate()
        return {
            "hours_used": d["hours_used"],
            "hours_remaining": d["hours_remaining"],
            "interval_hours": d["interval_hours"],
            "last_reset": d["last_reset"],
            "active": d["active"],
        }


class PlateLastResetSensor(_BasePlateSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, printer_name, unique_prefix, plate_id):
        super().__init__(coordinator, printer_name, unique_prefix, plate_id)
        self._attr_unique_id = f"{unique_prefix}_plate_{plate_id}_last_maintenance"
        self._attr_name = f"Plate {self._coordinator.get_plate_data(plate_id)['name']} Last Maintenance"

    @property
    def native_value(self):
        lr = self._plate()["last_reset"]
        return dt_util.parse_datetime(lr) if lr else None


class ActivePlateSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:layers"

    def __init__(self, coordinator, printer_name, unique_prefix):
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_active_plate"
        self._attr_name = "Active Plate"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    @property
    def native_value(self):
        pid = self._coordinator.get_active_plate_id()
        if pid:
            return self._coordinator.get_plate_data(pid)["name"]
        return None


def make_plate_sensors(coordinator, printer_name, unique_prefix, plate_id):
    return [
        PlateHoursUsedSensor(coordinator, printer_name, unique_prefix, plate_id),
        PlateHoursRemainingSensor(coordinator, printer_name, unique_prefix, plate_id),
        PlateStatusSensor(coordinator, printer_name, unique_prefix, plate_id),
        PlateLastResetSensor(coordinator, printer_name, unique_prefix, plate_id),
    ]


# ── Spool sensors ─────────────────────────────────────────────────────────────

class _BaseSpoolSensor(_BaseMaintenanceSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, printer_name, unique_prefix, spool_id):
        super().__init__(coordinator, printer_name, unique_prefix)
        self._spool_id = spool_id
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    def _spool(self):
        return self._coordinator.get_spool_data(self._spool_id)


class SpoolRemainingWeightSensor(_BaseSpoolSensor):
    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weight-gram"

    def __init__(self, coordinator, printer_name, unique_prefix, spool_id):
        super().__init__(coordinator, printer_name, unique_prefix, spool_id)
        self._attr_unique_id = f"{unique_prefix}_spool_{spool_id}_remaining"
        self._attr_name = f"Spool {self._coordinator.get_spool_data(spool_id)['name']} Remaining"

    @property
    def native_value(self):
        return round(self._spool()["remaining_weight_g"], 0)

    @property
    def extra_state_attributes(self):
        d = self._spool()
        return {
            "name": d["name"],
            "material": d["material"],
            "brand": d["brand"],
            "color": d["color"],
            "initial_weight_g": d["initial_weight_g"],
            "remaining_pct": d["remaining_pct"],
            "diameter_mm": d["diameter_mm"],
            "active": d["active"],
        }


class SpoolRemainingPctSensor(_BaseSpoolSensor):
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator, printer_name, unique_prefix, spool_id):
        super().__init__(coordinator, printer_name, unique_prefix, spool_id)
        self._attr_unique_id = f"{unique_prefix}_spool_{spool_id}_remaining_pct"
        self._attr_name = f"Spool {self._coordinator.get_spool_data(spool_id)['name']} Remaining %"

    @property
    def native_value(self):
        return self._spool()["remaining_pct"]


class ActiveSpoolSensor(_BaseMaintenanceSensor):
    _attr_icon = "mdi:spool"

    def __init__(self, coordinator, printer_name, unique_prefix):
        super().__init__(coordinator, printer_name, unique_prefix)
        self._attr_unique_id = f"{unique_prefix}_active_spool"
        self._attr_name = "Active Spool"
        self._attr_device_info = _device_info(DOMAIN, unique_prefix, printer_name)

    @property
    def native_value(self):
        sid = self._coordinator.get_active_spool_id()
        if sid:
            return self._coordinator.get_spool_data(sid)["name"]
        return None

    @property
    def extra_state_attributes(self):
        sid = self._coordinator.get_active_spool_id()
        if sid:
            d = self._coordinator.get_spool_data(sid)
            return {
                "material": d["material"],
                "brand": d["brand"],
                "color": d["color"],
                "remaining_weight_g": d["remaining_weight_g"],
                "remaining_pct": d["remaining_pct"],
            }
        return {}


def make_spool_sensors(coordinator, printer_name, unique_prefix, spool_id):
    return [
        SpoolRemainingWeightSensor(coordinator, printer_name, unique_prefix, spool_id),
        SpoolRemainingPctSensor(coordinator, printer_name, unique_prefix, spool_id),
    ]
