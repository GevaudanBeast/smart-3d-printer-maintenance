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
    CONF_COMPONENTS,
    CONF_FILAMENT_ENTITY,
    CONF_PRINTING_STATES,
    CONF_STATUS_ENTITY,
    DEFAULT_PRINTING_STATES,
    DOMAIN,
    SOON_THRESHOLD_PCT,
    STATUS_DUE,
    STATUS_OK,
    STATUS_OVERDUE,
    STATUS_SOON,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class PrinterMaintenanceCoordinator:
    """Manage print-time tracking and maintenance counters for one printer."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry.entry_id))
        self._data: dict[str, Any] = {}
        self._print_start_time: datetime | None = None
        self._unsubscribers: list[Any] = []
        # Entities register a callback here to receive update notifications
        self.listeners: list[Any] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def _opt(self, key: str, default: Any = None) -> Any:
        """Read a value from options first, then data, then default."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def status_entity(self) -> str:
        return self._opt(CONF_STATUS_ENTITY, "")

    @property
    def printing_states(self) -> list[str]:
        return self._opt(CONF_PRINTING_STATES, DEFAULT_PRINTING_STATES)

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
        elif remaining <= interval * SOON_THRESHOLD_PCT:
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

        if self.status_entity:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, [self.status_entity], self._handle_status_change
                )
            )
            # If the printer is already printing when HA starts, resume session
            current = self.hass.states.get(self.status_entity)
            if current and current.state in self.printing_states:
                saved_start = self._data.get("session_start")
                if saved_start:
                    try:
                        parsed = dt_util.parse_datetime(saved_start)
                        self._print_start_time = parsed if parsed else dt_util.utcnow()
                        _LOGGER.debug(
                            "Resumed ongoing print session started at %s",
                            self._print_start_time,
                        )
                    except (ValueError, TypeError):
                        self._print_start_time = dt_util.utcnow()
                else:
                    self._print_start_time = dt_util.utcnow()

    async def async_shutdown(self) -> None:
        """Unsubscribe listeners and persist current state."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        # Persist session_start so we can resume after restart
        await self._async_save_data()

    # ------------------------------------------------------------------
    # State change handler
    # ------------------------------------------------------------------

    @callback
    def _handle_status_change(self, event: Any) -> None:
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            return

        is_printing = new_state.state in self.printing_states
        was_printing = old_state is not None and old_state.state in self.printing_states

        if is_printing and not was_printing:
            self._print_start_time = dt_util.utcnow()
            self._data["session_start"] = self._print_start_time.isoformat()
            self.hass.async_create_task(self._async_save_data())
            _LOGGER.debug("Print session started")

        elif was_printing and not is_printing:
            if self._print_start_time:
                elapsed_hours = (
                    dt_util.utcnow() - self._print_start_time
                ).total_seconds() / 3600
                self._apply_print_hours(elapsed_hours)
                self._data["total_jobs"] = self._data.get("total_jobs", 0) + 1
                self._print_start_time = None
                self._data.pop("session_start", None)
                self.hass.async_create_task(self._async_save_data())
                _LOGGER.debug("Print session ended: %.2f h added", elapsed_hours)

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
            # Ensure all known components exist in stored data
            components = self._data.setdefault("components", {})
            for comp_id in COMPONENTS:
                components.setdefault(comp_id, {"hours_used": 0.0, "last_reset": None})
        else:
            self._data = {
                "total_print_hours": 0.0,
                "total_filament_m": 0.0,
                "total_jobs": 0,
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
        """Reset a component's usage counter."""
        components = self._data.setdefault("components", {})
        components.setdefault(component_id, {})
        components[component_id]["hours_used"] = 0.0
        components[component_id]["last_reset"] = dt_util.utcnow().isoformat()
        await self._async_save_data()
        self._notify_listeners()
        _LOGGER.info("Reset maintenance counter for component: %s", component_id)

    async def async_set_interval(self, component_id: str, interval_hours: float) -> None:
        """Update the maintenance interval for a component."""
        options = dict(self.entry.options)
        comp_opts = dict(options.get(CONF_COMPONENTS, {}))
        comp_opt = dict(comp_opts.get(component_id, {}))
        comp_opt["interval_hours"] = interval_hours
        comp_opts[component_id] = comp_opt
        options[CONF_COMPONENTS] = comp_opts
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self._notify_listeners()

    async def async_add_hours(
        self, hours: float, component_id: str | None = None
    ) -> None:
        """Manually add print hours (retroactive correction)."""
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
