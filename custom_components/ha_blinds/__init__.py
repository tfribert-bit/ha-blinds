"""HA Blinds integration entrypoint."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import (
    ATTR_ENTRY_ID,
    ATTR_MINUTES,
    DOMAIN,
    SERVICE_EVALUATE_NOW,
    SERVICE_PAUSE,
    SERVICE_RESUME,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from .coordinator import HaBlindsController

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "switch", "button"]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration domain."""
    import voluptuous as vol
    from homeassistant.core import ServiceCall
    from homeassistant.helpers import config_validation as cv
    from .coordinator import HaBlindsController

    SERVICE_SCHEMA_ENTRY = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})
    SERVICE_SCHEMA_PAUSE = vol.Schema(
        {
            vol.Optional(ATTR_ENTRY_ID): cv.string,
            vol.Optional(ATTR_MINUTES): vol.Coerce(int),
        }
    )

    hass.data.setdefault(DOMAIN, {})

    def _iter_targets(call: ServiceCall) -> list[HaBlindsController]:
        controllers = list(hass.data.get(DOMAIN, {}).values())
        entry_id = call.data.get(ATTR_ENTRY_ID)
        if not entry_id:
            return controllers
        target = hass.data.get(DOMAIN, {}).get(entry_id)
        return [target] if target else []

    async def _handle_pause(call: ServiceCall) -> None:
        minutes = call.data.get(ATTR_MINUTES)
        targets = _iter_targets(call)
        for controller in targets:
            await controller.async_pause(minutes)
        _LOGGER.debug("Pause service called for %s entries", len(targets))

    async def _handle_resume(call: ServiceCall) -> None:
        targets = _iter_targets(call)
        for controller in targets:
            await controller.async_resume()
        _LOGGER.debug("Resume service called for %s entries", len(targets))

    async def _handle_evaluate(call: ServiceCall) -> None:
        targets = _iter_targets(call)
        for controller in targets:
            await controller.async_evaluate_now()
        _LOGGER.debug("Evaluate now service called for %s entries", len(targets))

    if not hass.services.has_service(DOMAIN, SERVICE_PAUSE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PAUSE,
            _handle_pause,
            schema=SERVICE_SCHEMA_PAUSE,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESUME,
            _handle_resume,
            schema=SERVICE_SCHEMA_ENTRY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_EVALUATE_NOW,
            _handle_evaluate,
            schema=SERVICE_SCHEMA_ENTRY,
        )
        _LOGGER.debug("HA Blinds services registered")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Blinds from a config entry."""
    from .coordinator import HaBlindsController

    controller = HaBlindsController(hass, entry)
    await controller.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("HA Blinds entry %s setup complete", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .coordinator import HaBlindsController

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    controller: HaBlindsController | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if controller:
        await controller.async_stop()
        _LOGGER.info("HA Blinds entry %s unloaded", entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    try:
        await async_reload_entry(hass, entry)
    except Exception:
        _LOGGER.exception("Failed to reload HA Blinds entry %s after options update", entry.entry_id)
