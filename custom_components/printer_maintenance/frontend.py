"""Register the Lovelace custom card with Home Assistant's frontend."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

_LOGGER = logging.getLogger(__name__)

_URL_BASE = "/printer_maintenance"
_CARD_FILE = "printer-maintenance-card.js"
_REGISTERED_KEY = "printer_maintenance_frontend_registered"

async def _async_get_version(hass: HomeAssistant) -> str:
    """Version from the already loaded manifest (no file I/O in the event loop)."""
    try:
        integration = await async_get_integration(hass, "printer_maintenance")
    except Exception:  # noqa: BLE001
        return "0"
    return str(integration.version or "0")


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card JS file and tell the frontend to load it."""
    # Guard against double registration on config entry reload
    if hass.data.get(_REGISTERED_KEY):
        return

    www_path = Path(__file__).parent / "www"
    card_path = www_path / _CARD_FILE

    if not await hass.async_add_executor_job(card_path.exists):
        _LOGGER.warning("Lovelace card not found at %s — skipping registration", card_path)
        return

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path=_URL_BASE,
                    path=str(www_path),
                    cache_headers=False,
                )
            ]
        )
    except Exception as err:  # noqa: BLE001
        # Path may already be registered (integration reload without HA restart).
        # The file is still served; just continue to register the frontend URL.
        _LOGGER.debug("Static path %s already registered: %s", _URL_BASE, err)

    card_url = f"{_URL_BASE}/{_CARD_FILE}?v={await _async_get_version(hass)}"
    add_extra_js_url(hass, card_url)
    hass.data[_REGISTERED_KEY] = True
    _LOGGER.info("Registered Lovelace card at %s", card_url)
