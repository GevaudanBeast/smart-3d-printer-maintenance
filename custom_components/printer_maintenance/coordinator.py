"""Coordinator for 3D Printer Maintenance integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

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
    DEFAULT_PAUSED_STATES,
    DEFAULT_PRINTING_STATES,
    CONF_SOON_THRESHOLD,
    DEFAULT_SOON_THRESHOLD,
    DOMAIN,
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
            self._data["total_filament_m"] = (
                self._data.get("total_filament_m", 0.0) + delta
            )
            self._filament_unsaved_m += delta
            _LOGGER.debug("Filament +%.2f m (total %.2f m)", delta, self._data["total_filament_m"])
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
        else:
            self._apply_print_hours(hours)
        await self._async_save_data()
        self._notify_listeners()
