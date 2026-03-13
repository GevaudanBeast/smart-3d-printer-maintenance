"""Register the Lovelace custom card with Home Assistant's frontend."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_URL_BASE = "/printer_maintenance"
_CARD_FILE = "printer-maintenance-card.js"
_REGISTERED_KEY = "printer_maintenance_frontend_registered"

def _get_version() -> str:
    manifest = Path(__file__).parent / "manifest.json"
    try:
        return json.loads(manifest.read_text())["version"]
    except Exception:
        return "0"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card JS file and tell the frontend to load it."""
    # Guard against double registration on config entry reload
    if hass.data.get(_REGISTERED_KEY):
        return

    www_path = Path(__file__).parent / "www"
    card_path = www_path / _CARD_FILE

    if not card_path.exists():
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

    card_url = f"{_URL_BASE}/{_CARD_FILE}?v={_get_version()}"
    add_extra_js_url(hass, card_url)
    hass.data[_REGISTERED_KEY] = True
    _LOGGER.info("Registered Lovelace card at %s", card_url)
