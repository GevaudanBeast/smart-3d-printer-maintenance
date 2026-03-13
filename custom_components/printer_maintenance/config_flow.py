"""Config flow for 3D Printer Maintenance integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    COMPONENTS,
    CONF_COMPONENTS,
    CONF_FILAMENT_ENTITY,
    CONF_PRINTER_BRAND,
    CONF_PRINTER_MODEL,
    CONF_PRINTER_NAME,
    CONF_PRINTING_STATES,
    CONF_STATUS_ENTITY,
    CONF_COMPLETED_STATES,
    CONF_FAILURE_STATES,
    CONF_PAUSED_STATES,
    DEFAULT_COMPLETED_STATES,
    DEFAULT_FAILURE_STATES,
    DEFAULT_PAUSED_STATES,
    DEFAULT_PRINTING_STATES,
    DOMAIN,
    PRINTER_BRANDS,
)


class PrinterMaintenanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Printer Maintenance."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Printer identity."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_entities()

        schema = vol.Schema(
            {
                vol.Required(CONF_PRINTER_NAME, default="K1C"): selector.TextSelector(),
                vol.Required(CONF_PRINTER_BRAND, default="Creality"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=PRINTER_BRANDS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_PRINTER_MODEL, default="K1C"): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: HA entities for print status and filament."""
        if user_input is not None:
            raw_states = user_input.get(CONF_PRINTING_STATES, "printing")
            printing_states = [s.strip() for s in raw_states.split(",") if s.strip()]
            self._data[CONF_STATUS_ENTITY] = user_input[CONF_STATUS_ENTITY]
            self._data[CONF_PRINTING_STATES] = printing_states
            self._data[CONF_FILAMENT_ENTITY] = user_input.get(CONF_FILAMENT_ENTITY) or None
            self._data[CONF_COMPONENTS] = {}

            title = self._data.get(CONF_PRINTER_NAME, "3D Printer")
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema(
            {
                vol.Required(CONF_STATUS_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PRINTING_STATES, default="printing"
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
                vol.Optional(CONF_FILAMENT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )
        return self.async_show_form(
            step_id="entities",
            data_schema=schema,
            description_placeholders={"printing_states_hint": "printing, busy, ..."},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        # HA 2024.4+: self.config_entry is injected automatically into OptionsFlow
        return PrinterMaintenanceOptionsFlow()


class PrinterMaintenanceOptionsFlow(OptionsFlow):
    """Handle options (intervals, entities).

    HA 2024.4+: self.config_entry is injected automatically by the base class.
    """

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        # Initialise lazily so self.config_entry is already available
        if not self._options:
            self._options = dict(self.config_entry.options)

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_intervals()

        current_states = self.config_entry.options.get(
            CONF_PRINTING_STATES,
            self.config_entry.data.get(CONF_PRINTING_STATES, DEFAULT_PRINTING_STATES),
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATUS_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_STATUS_ENTITY,
                        self.config_entry.data.get(CONF_STATUS_ENTITY, ""),
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PRINTING_STATES,
                    default=", ".join(current_states),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_FILAMENT_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_FILAMENT_ENTITY,
                        self.config_entry.data.get(CONF_FILAMENT_ENTITY, ""),
                    )
                    or "",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PAUSED_STATES,
                    default=", ".join(
                        self.config_entry.options.get(
                            CONF_PAUSED_STATES,
                            self.config_entry.data.get(CONF_PAUSED_STATES, DEFAULT_PAUSED_STATES),
                        )
                    ),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_COMPLETED_STATES,
                    default=", ".join(
                        self.config_entry.options.get(
                            CONF_COMPLETED_STATES,
                            self.config_entry.data.get(CONF_COMPLETED_STATES, DEFAULT_COMPLETED_STATES),
                        )
                    ),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_FAILURE_STATES,
                    default=", ".join(
                        self.config_entry.options.get(
                            CONF_FAILURE_STATES,
                            self.config_entry.data.get(CONF_FAILURE_STATES, DEFAULT_FAILURE_STATES),
                        )
                    ),
                ): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_intervals(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure maintenance intervals for each component."""
        if user_input is not None:
            comp_opts: dict[str, Any] = dict(self._options.get(CONF_COMPONENTS, {}))
            for comp_id in COMPONENTS:
                key = f"interval_{comp_id}"
                if key in user_input:
                    comp_opts.setdefault(comp_id, {})
                    comp_opts[comp_id]["interval_hours"] = float(user_input[key])
            self._options[CONF_COMPONENTS] = comp_opts
            raw = self._options.get(CONF_PRINTING_STATES, "printing")
            if isinstance(raw, str):
                self._options[CONF_PRINTING_STATES] = [
                    s.strip() for s in raw.split(",") if s.strip()
                ]
            for key in (CONF_PAUSED_STATES, CONF_COMPLETED_STATES, CONF_FAILURE_STATES):
                raw_k = self._options.get(key, "")
                if isinstance(raw_k, str):
                    self._options[key] = [s.strip() for s in raw_k.split(",") if s.strip()]
            return self.async_create_entry(data=self._options)

        current_comp_opts: dict[str, Any] = self._options.get(CONF_COMPONENTS, {})
        fields: dict[Any, Any] = {}
        for comp_id, info in COMPONENTS.items():
            default_interval = current_comp_opts.get(comp_id, {}).get(
                "interval_hours", info["default_interval"]
            )
            fields[
                vol.Required(f"interval_{comp_id}", default=int(default_interval))
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=10000,
                    step=1,
                    unit_of_measurement="h",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )

        return self.async_show_form(
            step_id="intervals", data_schema=vol.Schema(fields)
        )
