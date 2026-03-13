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
        _LOGGER.debug("Lovelace card already registered — skipping")
        return

    card_path = Path(__file__).parent / "www" / _CARD_FILE

    if not card_path.exists():
        _LOGGER.error(
            "Lovelace card not found at %s — the custom card will not work", card_path
        )
        return

    url = f"{_URL_BASE}/{_CARD_FILE}"

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path=url,
                    path=str(card_path),
                    cache_headers=False,
                )
            ]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.error(
            "Failed to register static path for Lovelace card at %s: %s", url, err
        )
        return

    add_extra_js_url(hass, url)
    hass.data[_REGISTERED_KEY] = True
    _LOGGER.warning(
        "Lovelace card registered and served at %s — if the card still does not "
        "appear, add the resource manually in HA: Settings → Dashboards → Resources → %s",
        url,
        url,
    )
