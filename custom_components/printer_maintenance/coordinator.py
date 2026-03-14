"""Coordinator for 3D Printer Maintenance integration."""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    COMPONENTS,
    CONF_COMPLETED_STATES,
    CONF_COMPONENTS,
    CONF_FILAMENT_ENTITY,
    CONF_FAILURE_STATES,
    CONF_INITIAL_FILAMENT,
    CONF_INITIAL_HOURS,
    CONF_PAUSED_STATES,
    CONF_PRINTING_STATES,
    CONF_STATUS_ENTITY,
    DEFAULT_COMPLETED_STATES,
    DEFAULT_FAILURE_STATES,
    DEFAULT_FILAMENT_DIAMETER_MM,
    DEFAULT_PAUSED_STATES,
    DEFAULT_PLATE_INTERVAL,
    DEFAULT_PRINTING_STATES,
    CONF_SOON_THRESHOLD,
    DEFAULT_SOON_THRESHOLD,
    DOMAIN,
    MATERIAL_DENSITIES,
    STATUS_DUE,
    STATUS_OK,
    STATUS_OVERDUE,
    STATUS_SOON,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Minimum session duration to be counted as a real job (avoids false counts
# from brief status flickers or accidental cancellations).
_MIN_JOB_HOURS = 1 / 60  # 1 minute

# Minimum filament delta (m) before persisting to storage — avoids hammering
# disk on every sensor tick. In-memory value and listener notifications are
# still updated on every change for real-time display.
_MIN_FILAMENT_SAVE_M = 0.05


class PrinterMaintenanceCoordinator:
    """Manage print-time tracking and maintenance counters for one printer."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry.entry_id))
        self._data: dict[str, Any] = {}
        # Current printing segment start time (None when paused or idle)
        self._print_start_time: datetime | None = None
        # Hours accumulated in previous segments of the same session (across pauses)
        self._session_hours: float = 0.0
        # Last known filament entity value (for delta computation)
        self._last_filament_value: float | None = None
        # Filament accumulated since last disk save (throttle I/O)
        self._filament_unsaved_m: float = 0.0
        self._unsubscribers: list[Any] = []
        self.listeners: list[Any] = []
        # Components for which a "due/overdue" notification has already been sent.
        # Cleared when the component is reset (back to ok).
        self._notified_due: set[str] = set()
        # Dynamic entity registration callbacks (set by sensor.py / button.py)
        self._plate_sensor_add_fn = None
        self._plate_button_add_fn = None
        self._spool_sensor_add_fn = None
        self._spool_button_add_fn = None
        # Entity references for dynamic removal
        self._plate_sensor_entities: dict[str, list] = {}
        self._plate_button_entities: dict[str, list] = {}
        self._spool_sensor_entities: dict[str, list] = {}
        self._spool_button_entities: dict[str, list] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def _opt(self, key: str, default: Any = None) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def status_entity(self) -> str:
        return self._opt(CONF_STATUS_ENTITY, "")

    @property
    def printing_states(self) -> list[str]:
        return self._opt(CONF_PRINTING_STATES, DEFAULT_PRINTING_STATES)

    @property
    def paused_states(self) -> list[str]:
        return self._opt(CONF_PAUSED_STATES, DEFAULT_PAUSED_STATES)

    @property
    def completed_states(self) -> list[str]:
        return self._opt(CONF_COMPLETED_STATES, DEFAULT_COMPLETED_STATES)

    @property
    def failure_states(self) -> list[str]:
        return self._opt(CONF_FAILURE_STATES, DEFAULT_FAILURE_STATES)

    @property
    def soon_threshold_pct(self) -> float:
        """Return the 'soon' alert threshold as a fraction (e.g. 0.20 for 20%)."""
        return self._opt(CONF_SOON_THRESHOLD, DEFAULT_SOON_THRESHOLD) / 100

    @property
    def filament_entity(self) -> str | None:
        return self._opt(CONF_FILAMENT_ENTITY)

    @property
    def total_print_hours(self) -> float:
        return self._data.get("total_print_hours", 0.0)

    @property
    def total_filament_m(self) -> float:
        return self._data.get("total_filament_m", 0.0)

    @property
    def total_jobs(self) -> int:
        return self._data.get("total_jobs", 0)

    @property
    def total_jobs_ok(self) -> int:
        return self._data.get("total_jobs_ok", 0)

    @property
    def total_jobs_ko(self) -> int:
        return self._data.get("total_jobs_ko", 0)

    @property
    def is_currently_printing(self) -> bool:
        return self._print_start_time is not None

    # ------------------------------------------------------------------
    # Component data
    # ------------------------------------------------------------------

    def _component_interval(self, component_id: str) -> float:
        default = COMPONENTS[component_id]["default_interval"]
        comp_opts = self._opt(CONF_COMPONENTS, {})
        return float(comp_opts.get(component_id, {}).get("interval_hours", default))

    def get_component_data(self, component_id: str) -> dict[str, Any]:
        comp = self._data.get("components", {}).get(component_id, {})
        interval = self._component_interval(component_id)
        hours_used = comp.get("hours_used", 0.0)
        remaining = max(0.0, interval - hours_used)

        if hours_used > interval:
            status = STATUS_OVERDUE
        elif hours_used >= interval:
            status = STATUS_DUE
        elif remaining <= interval * self.soon_threshold_pct:
            status = STATUS_SOON
        else:
            status = STATUS_OK

        return {
            "hours_used": round(hours_used, 1),
            "interval_hours": interval,
            "hours_remaining": round(remaining, 1),
            "status": status,
            "last_reset": comp.get("last_reset"),
        }

    # ------------------------------------------------------------------
    # Setup / shutdown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Load persisted data and subscribe to state changes."""
        await self._async_load_data()

        if not self.status_entity:
            return

        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass, [self.status_entity], self._handle_status_change
            )
        )

        # Subscribe to filament entity for incremental tracking
        if self.filament_entity:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, [self.filament_entity], self._handle_filament_change
                )
            )
            fil_state = self.hass.states.get(self.filament_entity)
            if fil_state and fil_state.state not in ("unknown", "unavailable"):
                try:
                    self._last_filament_value = float(fil_state.state)
                except ValueError:
                    pass

        # Restore in-progress session after HA restart
        current = self.hass.states.get(self.status_entity)
        if current is None:
            return

        state = current.state
        if state in self.printing_states:
            self._session_hours = self._data.get("session_hours", 0.0)
            saved_start = self._data.get("session_start")
            if saved_start:
                parsed = dt_util.parse_datetime(saved_start)
                self._print_start_time = parsed if parsed else dt_util.utcnow()
                _LOGGER.debug("Resumed printing session from %s", self._print_start_time)
            else:
                self._print_start_time = dt_util.utcnow()

        elif state in self.paused_states:
            # Session paused: restore accumulated hours, no active segment
            self._session_hours = self._data.get("session_hours", 0.0)
            _LOGGER.debug("Restored paused session (%.2f h so far)", self._session_hours)

    async def async_shutdown(self) -> None:
        """Unsubscribe and persist state (flush any pending filament data)."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        self._filament_unsaved_m = 0.0  # clear counter before final save
        await self._async_save_data()

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    @callback
    def _handle_status_change(self, event: Any) -> None:
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            return

        new = new_state.state
        old = old_state.state if old_state else None

        is_printing = new in self.printing_states
        was_printing = old in self.printing_states
        is_paused = new in self.paused_states
        was_paused = old in self.paused_states

        # ── Print started (from idle, stopped, OR resumed from pause) ────────
        if is_printing and not was_printing:
            if not was_paused:
                # Fresh session start
                self._session_hours = 0.0
                self._data["session_hours"] = 0.0
            # Mark start of this printing segment
            self._print_start_time = dt_util.utcnow()
            self._data["session_start"] = self._print_start_time.isoformat()
            self.hass.async_create_task(self._async_save_data())
            _LOGGER.debug("Print segment started (session_hours=%.2f)", self._session_hours)

        # ── Paused (from printing) ────────────────────────────────────────────
        elif is_paused and was_printing:
            if self._print_start_time:
                elapsed = (dt_util.utcnow() - self._print_start_time).total_seconds() / 3600
                self._session_hours += elapsed
                self._print_start_time = None
            self._data["session_hours"] = self._session_hours
            self._data.pop("session_start", None)
            self.hass.async_create_task(self._async_save_data())
            _LOGGER.debug("Print paused (session_hours=%.2f)", self._session_hours)

        # ── Session ended (from printing or paused → any final state) ─────────
        elif not is_printing and not is_paused and (was_printing or was_paused):
            if self._print_start_time:
                elapsed = (dt_util.utcnow() - self._print_start_time).total_seconds() / 3600
                self._session_hours += elapsed
                self._print_start_time = None

            total = self._session_hours
            self._session_hours = 0.0

            if total >= _MIN_JOB_HOURS:
                self._apply_print_hours(total)
                if new in self.completed_states:
                    self._data["total_jobs_ok"] = self._data.get("total_jobs_ok", 0) + 1
                    self._data["total_jobs"] = self._data.get("total_jobs", 0) + 1
                    _LOGGER.debug("Job OK — %.2f h added", total)
                elif new in self.failure_states:
                    self._data["total_jobs_ko"] = self._data.get("total_jobs_ko", 0) + 1
                    self._data["total_jobs"] = self._data.get("total_jobs", 0) + 1
                    _LOGGER.debug("Job KO (%s) — %.2f h added", new, total)
                else:
                    # Any other state (idle, standby, …): hours counted, no job flagged
                    _LOGGER.debug(
                        "Session ended in unclassified state '%s' — %.2f h added, no job counted",
                        new, total,
                    )
            else:
                _LOGGER.debug(
                    "Session too short (%.1f s) — not counted", total * 3600
                )

            self._data.pop("session_start", None)
            self._data.pop("session_hours", None)
            self.hass.async_create_task(self._async_save_data())

        self._notify_listeners()

    @callback
    def _handle_filament_change(self, event: Any) -> None:
        """Accumulate filament consumption in real time during active printing."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            new_val = float(new_state.state)
        except ValueError:
            return

        old_val = self._last_filament_value
        self._last_filament_value = new_val

        # Only accumulate while actively printing (not paused, not idle)
        if not self.is_currently_printing:
            return

        if old_val is not None and new_val > old_val:
            delta = new_val - old_val
            unit = (new_state.attributes.get("unit_of_measurement") or "m").lower()
            if unit == "mm":
                delta /= 1000.0
            elif unit == "cm":
                delta /= 100.0
            self._data["total_filament_m"] = (
                self._data.get("total_filament_m", 0.0) + delta
            )
            self._filament_unsaved_m += delta
            _LOGGER.debug("Filament +%.2f m (total %.2f m)", delta, self._data["total_filament_m"])
            active_spool = self.get_active_spool_id()
            if active_spool:
                spools = self._data.setdefault("spools", {})
                if active_spool in spools:
                    grams = self._grams_from_meters(active_spool, delta)
                    spools[active_spool]["remaining_weight_g"] = max(
                        0.0,
                        spools[active_spool].get("remaining_weight_g", 0.0) - grams
                    )
            # Persist only when unsaved accumulation crosses the threshold
            if self._filament_unsaved_m >= _MIN_FILAMENT_SAVE_M:
                self._filament_unsaved_m = 0.0
                self.hass.async_create_task(self._async_save_data())
            self._notify_listeners()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_print_hours(self, hours: float) -> None:
        """Add print hours to global total and all component counters."""
        self._data["total_print_hours"] = (
            self._data.get("total_print_hours", 0.0) + hours
        )
        components = self._data.setdefault("components", {})
        for comp_id in COMPONENTS:
            comp = components.setdefault(comp_id, {"hours_used": 0.0, "last_reset": None})
            comp["hours_used"] = comp.get("hours_used", 0.0) + hours
        active_plate = self.get_active_plate_id()
        if active_plate:
            plates = self._data.setdefault("plates", {})
            if active_plate in plates:
                plates[active_plate]["hours_used"] = plates[active_plate].get("hours_used", 0.0) + hours
        self._check_and_notify_maintenance()

    def _check_and_notify_maintenance(self) -> None:
        """Send a HA persistent notification for each component that is due or overdue."""
        printer_name = self.entry.data.get("printer_name", "Printer")
        for comp_id, comp_info in COMPONENTS.items():
            data = self.get_component_data(comp_id)
            status = data["status"]
            notif_id = f"printer_maintenance_{self.entry.entry_id}_{comp_id}"
            if status in (STATUS_DUE, STATUS_OVERDUE):
                if comp_id not in self._notified_due:
                    self._notified_due.add(comp_id)
                    label = STATUS_OVERDUE if status == STATUS_OVERDUE else STATUS_DUE
                    persistent_notification.async_create(
                        self.hass,
                        message=(
                            f"**{comp_info['name']}** needs maintenance on **{printer_name}**.\n"
                            f"Hours used: {data['hours_used']} h / {data['interval_hours']} h "
                            f"({label})."
                        ),
                        title=f"🔧 {printer_name} — Maintenance {label}",
                        notification_id=notif_id,
                    )
                    _LOGGER.info(
                        "Maintenance notification sent for %s (%s) — %s",
                        comp_id, printer_name, label,
                    )
            else:
                # Status back to ok/soon: clear notification and tracking
                if comp_id in self._notified_due:
                    self._notified_due.discard(comp_id)
                    persistent_notification.async_dismiss(self.hass, notif_id)
        # Check active plate
        active_plate = self.get_active_plate_id()
        if active_plate:
            plate_data = self.get_plate_data(active_plate)
            plate_status = plate_data["status"]
            plate_notif_key = f"plate_{active_plate}"
            notif_id = f"printer_maintenance_{self.entry.entry_id}_plate_{active_plate}"
            if plate_status in (STATUS_DUE, STATUS_OVERDUE):
                if plate_notif_key not in self._notified_due:
                    self._notified_due.add(plate_notif_key)
                    label = STATUS_OVERDUE if plate_status == STATUS_OVERDUE else STATUS_DUE
                    persistent_notification.async_create(
                        self.hass,
                        message=(
                            f"**Plate {plate_data['name']}** needs maintenance on **{printer_name}**.\n"
                            f"Hours used: {plate_data['hours_used']} h / {plate_data['interval_hours']} h "
                            f"({label})."
                        ),
                        title=f"🔧 {printer_name} — Plate Maintenance {label}",
                        notification_id=notif_id,
                    )
                    _LOGGER.info(
                        "Plate maintenance notification sent for %s (%s) — %s",
                        active_plate, printer_name, label,
                    )
            else:
                if plate_notif_key in self._notified_due:
                    self._notified_due.discard(plate_notif_key)
                    persistent_notification.async_dismiss(self.hass, notif_id)

    async def _async_load_data(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data = stored
            components = self._data.setdefault("components", {})
            for comp_id in COMPONENTS:
                components.setdefault(comp_id, {"hours_used": 0.0, "last_reset": None})
        else:
            initial_hours = float(self.entry.data.get(CONF_INITIAL_HOURS, 0))
            initial_filament = float(self.entry.data.get(CONF_INITIAL_FILAMENT, 0))
            self._data = {
                "total_print_hours": initial_hours,
                "total_filament_m": initial_filament,
                "total_jobs": 0,
                "total_jobs_ok": 0,
                "total_jobs_ko": 0,
                "components": {
                    comp_id: {"hours_used": 0.0, "last_reset": None}
                    for comp_id in COMPONENTS
                },
            }
        self._data.setdefault("plates", {})
        self._data.setdefault("spools", {})

    async def _async_save_data(self) -> None:
        await self._store.async_save(self._data)

    def _notify_listeners(self) -> None:
        for listener in self.listeners:
            listener()

    # ------------------------------------------------------------------
    # Public actions (called by buttons / services)
    # ------------------------------------------------------------------

    async def async_reset_component(self, component_id: str) -> None:
        components = self._data.setdefault("components", {})
        components.setdefault(component_id, {})
        components[component_id]["hours_used"] = 0.0
        components[component_id]["last_reset"] = dt_util.utcnow().isoformat()
        await self._async_save_data()
        # Dismiss notification and clear tracking if the component was due/overdue
        if component_id in self._notified_due:
            self._notified_due.discard(component_id)
            notif_id = f"printer_maintenance_{self.entry.entry_id}_{component_id}"
            persistent_notification.async_dismiss(self.hass, notif_id)
        self._notify_listeners()
        _LOGGER.info("Reset maintenance counter for component: %s", component_id)

    async def async_set_interval(self, component_id: str, interval_hours: float) -> None:
        options = dict(self.entry.options)
        comp_opts = dict(options.get(CONF_COMPONENTS, {}))
        comp_opt = dict(comp_opts.get(component_id, {}))
        comp_opt["interval_hours"] = interval_hours
        comp_opts[component_id] = comp_opt
        options[CONF_COMPONENTS] = comp_opts
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self._notify_listeners()

    async def async_set_total_hours(self, hours: float) -> None:
        """Set the global print-hour total without touching component counters."""
        self._data["total_print_hours"] = hours
        await self._async_save_data()
        self._notify_listeners()

    async def async_set_total_filament(self, meters: float) -> None:
        """Set the global filament total without touching component counters."""
        self._data["total_filament_m"] = meters
        await self._async_save_data()
        self._notify_listeners()

    async def async_add_hours(
        self, hours: float, component_id: str | None = None
    ) -> None:
        if component_id:
            components = self._data.setdefault("components", {})
            comp = components.setdefault(
                component_id, {"hours_used": 0.0, "last_reset": None}
            )
            comp["hours_used"] = comp.get("hours_used", 0.0) + hours
            self._check_and_notify_maintenance()
        else:
            self._apply_print_hours(hours)
        await self._async_save_data()
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Static / instance helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        return re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')

    def _grams_from_meters(self, spool_id: str, meters: float) -> float:
        spool = self._data.get("spools", {}).get(spool_id, {})
        material = spool.get("material", "PLA")
        diameter_mm = spool.get("diameter_mm", DEFAULT_FILAMENT_DIAMETER_MM)
        density = MATERIAL_DENSITIES.get(material, MATERIAL_DENSITIES["Other"])
        radius_cm = (diameter_mm / 2.0) / 10.0
        volume_per_m = math.pi * radius_cm ** 2 * 100.0
        return meters * volume_per_m * density

    # ------------------------------------------------------------------
    # Plate methods
    # ------------------------------------------------------------------

    def get_all_plates(self) -> dict:
        return self._data.get("plates", {})

    def get_active_plate_id(self) -> str | None:
        for pid, p in self._data.get("plates", {}).items():
            if p.get("active"):
                return pid
        return None

    def get_plate_data(self, plate_id: str) -> dict:
        plates = self._data.get("plates", {})
        p = plates.get(plate_id, {})
        interval = float(p.get("interval_hours", DEFAULT_PLATE_INTERVAL))
        hours_used = p.get("hours_used", 0.0)
        remaining = max(0.0, interval - hours_used)
        if hours_used > interval:
            status = STATUS_OVERDUE
        elif hours_used >= interval:
            status = STATUS_DUE
        elif remaining <= interval * self.soon_threshold_pct:
            status = STATUS_SOON
        else:
            status = STATUS_OK
        return {
            "name": p.get("name", plate_id),
            "hours_used": round(hours_used, 1),
            "interval_hours": interval,
            "hours_remaining": round(remaining, 1),
            "status": status,
            "last_reset": p.get("last_reset"),
            "active": p.get("active", False),
        }

    async def async_add_plate(self, name: str, interval_hours: float) -> str:
        slug = self._slugify(name)
        plates = self._data.setdefault("plates", {})
        is_first = len(plates) == 0
        plate_id = slug
        i = 2
        while plate_id in plates:
            plate_id = f"{slug}_{i}"
            i += 1
        plates[plate_id] = {
            "name": name,
            "hours_used": 0.0,
            "last_reset": None,
            "active": is_first,
            "interval_hours": interval_hours,
        }
        await self._async_save_data()
        if self._plate_sensor_add_fn:
            printer_name = self.entry.data.get("printer_name", "Printer")
            from .sensor import make_plate_sensors
            entities = make_plate_sensors(self, printer_name, self.entry.entry_id, plate_id)
            self._plate_sensor_entities[plate_id] = entities
            self._plate_sensor_add_fn(entities)
        if self._plate_button_add_fn:
            printer_name = self.entry.data.get("printer_name", "Printer")
            from .button import make_plate_buttons
            entities = make_plate_buttons(self, printer_name, self.entry.entry_id, plate_id, name)
            self._plate_button_entities[plate_id] = entities
            self._plate_button_add_fn(entities)
        self._notify_listeners()
        _LOGGER.info("Added plate: %s (%s)", plate_id, name)
        return plate_id

    async def async_remove_plate(self, plate_id: str) -> None:
        plates = self._data.get("plates", {})
        if plate_id not in plates:
            return
        was_active = plates[plate_id].get("active", False)
        del plates[plate_id]
        if was_active and plates:
            next_id = next(iter(plates))
            plates[next_id]["active"] = True
        await self._async_save_data()
        for entity in self._plate_sensor_entities.pop(plate_id, []):
            self.hass.async_create_task(entity.async_remove())
        for entity in self._plate_button_entities.pop(plate_id, []):
            self.hass.async_create_task(entity.async_remove())
        self._notify_listeners()

    async def async_set_active_plate(self, plate_id: str) -> None:
        plates = self._data.get("plates", {})
        if plate_id not in plates:
            return
        for pid in plates:
            plates[pid]["active"] = (pid == plate_id)
        await self._async_save_data()
        self._notify_listeners()

    async def async_reset_plate(self, plate_id: str) -> None:
        plates = self._data.get("plates", {})
        if plate_id not in plates:
            return
        plates[plate_id]["hours_used"] = 0.0
        plates[plate_id]["last_reset"] = dt_util.utcnow().isoformat()
        notif_id = f"printer_maintenance_{self.entry.entry_id}_plate_{plate_id}"
        persistent_notification.async_dismiss(self.hass, notif_id)
        await self._async_save_data()
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Spool methods
    # ------------------------------------------------------------------

    def get_all_spools(self) -> dict:
        return self._data.get("spools", {})

    def get_active_spool_id(self) -> str | None:
        for sid, s in self._data.get("spools", {}).items():
            if s.get("active"):
                return sid
        return None

    def get_spool_data(self, spool_id: str) -> dict:
        s = self._data.get("spools", {}).get(spool_id, {})
        initial = s.get("initial_weight_g", 1000.0)
        remaining = s.get("remaining_weight_g", initial)
        pct = round(remaining / initial * 100, 1) if initial > 0 else 0.0
        return {
            "name": s.get("name", spool_id),
            "material": s.get("material", "PLA"),
            "color": s.get("color", ""),
            "brand": s.get("brand", ""),
            "initial_weight_g": round(initial, 0),
            "remaining_weight_g": round(remaining, 1),
            "remaining_pct": pct,
            "diameter_mm": s.get("diameter_mm", DEFAULT_FILAMENT_DIAMETER_MM),
            "active": s.get("active", False),
        }

    async def async_add_spool(
        self, name: str, material: str, brand: str, color: str,
        initial_weight_g: float, diameter_mm: float
    ) -> str:
        slug = self._slugify(name)
        spools = self._data.setdefault("spools", {})
        is_first = len(spools) == 0
        spool_id = slug
        i = 2
        while spool_id in spools:
            spool_id = f"{slug}_{i}"
            i += 1
        spools[spool_id] = {
            "name": name,
            "material": material,
            "brand": brand,
            "color": color,
            "initial_weight_g": initial_weight_g,
            "remaining_weight_g": initial_weight_g,
            "diameter_mm": diameter_mm,
            "active": is_first,
        }
        await self._async_save_data()
        if self._spool_sensor_add_fn:
            printer_name = self.entry.data.get("printer_name", "Printer")
            from .sensor import make_spool_sensors
            entities = make_spool_sensors(self, printer_name, self.entry.entry_id, spool_id)
            self._spool_sensor_entities[spool_id] = entities
            self._spool_sensor_add_fn(entities)
        if self._spool_button_add_fn:
            printer_name = self.entry.data.get("printer_name", "Printer")
            from .button import make_spool_buttons
            entities = make_spool_buttons(self, printer_name, self.entry.entry_id, spool_id, name)
            self._spool_button_entities[spool_id] = entities
            self._spool_button_add_fn(entities)
        self._notify_listeners()
        _LOGGER.info("Added spool: %s (%s %s)", spool_id, material, name)
        return spool_id

    async def async_remove_spool(self, spool_id: str) -> None:
        spools = self._data.get("spools", {})
        if spool_id not in spools:
            return
        was_active = spools[spool_id].get("active", False)
        del spools[spool_id]
        if was_active and spools:
            next_id = next(iter(spools))
            spools[next_id]["active"] = True
        await self._async_save_data()
        for entity in self._spool_sensor_entities.pop(spool_id, []):
            self.hass.async_create_task(entity.async_remove())
        for entity in self._spool_button_entities.pop(spool_id, []):
            self.hass.async_create_task(entity.async_remove())
        self._notify_listeners()

    async def async_set_active_spool(self, spool_id: str) -> None:
        spools = self._data.get("spools", {})
        if spool_id not in spools:
            return
        for sid in spools:
            spools[sid]["active"] = (sid == spool_id)
        self._last_filament_value = None
        await self._async_save_data()
        self._notify_listeners()

    async def async_update_spool_weight(self, spool_id: str, remaining_weight_g: float) -> None:
        spools = self._data.get("spools", {})
        if spool_id not in spools:
            return
        spools[spool_id]["remaining_weight_g"] = remaining_weight_g
        await self._async_save_data()
        self._notify_listeners()
