"""Constants for the 3D Printer Maintenance integration."""
from __future__ import annotations

DOMAIN = "printer_maintenance"
STORAGE_VERSION = 1
STORAGE_KEY = "printer_maintenance_{}"

# Config / options keys
CONF_PRINTER_NAME = "printer_name"
CONF_PRINTER_BRAND = "printer_brand"
CONF_PRINTER_MODEL = "printer_model"
CONF_STATUS_ENTITY = "status_entity"
CONF_PRINTING_STATES = "printing_states"
CONF_PAUSED_STATES = "paused_states"
CONF_COMPLETED_STATES = "completed_states"
CONF_FAILURE_STATES = "failure_states"
CONF_SOON_THRESHOLD = "soon_threshold_pct"
CONF_FILAMENT_ENTITY = "filament_entity"
CONF_COMPONENTS = "components"

# Platforms
PLATFORMS = ["sensor", "button"]

# Maintenance status values
STATUS_OK = "ok"
STATUS_SOON = "soon"
STATUS_DUE = "due"
STATUS_OVERDUE = "overdue"

# Default: alert when remaining life < 20% of interval (configurable, stored as %)
SOON_THRESHOLD_PCT = 0.20
DEFAULT_SOON_THRESHOLD = 20  # percent

DEFAULT_PRINTING_STATES = ["printing"]
# States where the session is paused but NOT ended (time stops, no job count yet)
DEFAULT_PAUSED_STATES = ["paused", "pause"]
# States that mean a successful completion → jobs_ok
DEFAULT_COMPLETED_STATES = ["completed", "complete", "finish"]
# States that mean an explicit failure → jobs_ko (anything else = ignored)
DEFAULT_FAILURE_STATES = ["stopped", "error", "cancelled", "failed"]

# Supported printer brands
PRINTER_BRANDS = [
    "Creality",
    "Bambu Lab",
    "Prusa",
    "Voron",
    "Sovol",
    "Artillery",
    "Other",
]

# Components tracked with default maintenance intervals (hours)
COMPONENTS: dict[str, dict] = {
    # Extrusion
    "nozzle": {
        "name": "Nozzle",
        "default_interval": 300,
        "icon": "mdi:printer-3d-nozzle",
        "category": "extrusion",
    },
    "heatbreak": {
        "name": "Heatbreak",
        "default_interval": 500,
        "icon": "mdi:heat-wave",
        "category": "extrusion",
    },
    "extruder_gear": {
        "name": "Extruder Gear",
        "default_interval": 400,
        "icon": "mdi:cog-outline",
        "category": "extrusion",
    },
    # Movement
    "belts": {
        "name": "Belts",
        "default_interval": 800,
        "icon": "mdi:link-variant",
        "category": "movement",
    },
    "linear_rods": {
        "name": "Linear Rods",
        "default_interval": 600,
        "icon": "mdi:ray-end-arrow",
        "category": "movement",
    },
    "linear_rails": {
        "name": "Linear Rails",
        "default_interval": 600,
        "icon": "mdi:train",
        "category": "movement",
    },
    # Platform
    "build_plate": {
        "name": "Build Plate",
        "default_interval": 1000,
        "icon": "mdi:grid",
        "category": "platform",
    },
    "build_surface": {
        "name": "Build Surface",
        "default_interval": 200,
        "icon": "mdi:texture-box",
        "category": "platform",
    },
    # Cooling
    "hotend_fan": {
        "name": "Hotend Fan",
        "default_interval": 600,
        "icon": "mdi:fan",
        "category": "cooling",
    },
    "part_cooling_fan": {
        "name": "Part Cooling Fan",
        "default_interval": 600,
        "icon": "mdi:fan-chevron-down",
        "category": "cooling",
    },
    # Misc
    "ptfe_tube": {
        "name": "PTFE Tube",
        "default_interval": 400,
        "icon": "mdi:pipe",
        "category": "misc",
    },
}
