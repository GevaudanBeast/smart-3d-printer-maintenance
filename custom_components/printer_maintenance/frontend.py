"""Register the Lovelace custom card with Home Assistant's frontend."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_URL_BASE = "/printer_maintenance"
_CARD_FILE = "printer-maintenance-card.js"
_REGISTERED_KEY = "printer_maintenance_frontend_registered"


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
        _LOGGER.warning("Could not register static path %s: %s", _URL_BASE, err)
        return

    card_url = f"{_URL_BASE}/{_CARD_FILE}"
    add_extra_js_url(hass, card_url)
    hass.data[_REGISTERED_KEY] = True
    _LOGGER.info("Registered Lovelace card at %s", card_url)
