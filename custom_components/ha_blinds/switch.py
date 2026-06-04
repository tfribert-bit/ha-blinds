"""Switch entities for HA Blinds."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_HEAT_PROTECTION,
    CONF_ENABLE_HIGH_LUX_PROTECTION,
    CONF_ENABLE_LOW_LUX_REOPEN,
    CONF_ENABLE_PRIVACY_HOUR,
    CONF_ENABLE_SUN_ELEVATION_TRACKING,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    from .coordinator import HaBlindsController

    coordinator: HaBlindsController = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HaBlindsAutomationSwitch(coordinator, entry),
        HaBlindsPrivacyHourSwitch(coordinator, entry),
        HaBlindsHighLuxProtectionSwitch(coordinator, entry),
        HaBlindsHeatProtectionSwitch(coordinator, entry),
        HaBlindsLowLuxReopenSwitch(coordinator, entry),
        HaBlindsSunElevationTrackingSwitch(coordinator, entry),
    ]

    async_add_entities(entities)


class HaBlindsBaseSwitch(SwitchEntity):
    """Base switch."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self.entry = entry

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "HA Blinds",
            "manufacturer": "HA Blinds",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    def _cfg(self, key: str) -> Any:
        return self.coordinator._cfg(key)

    async def _async_update_config(self, key: str, value: bool) -> None:
        """Update configuration."""
        try:
            options = dict(self.entry.options)
            options[key] = value
            self.hass.config_entries.async_update_entry(self.entry, options=options)
            # Trigger immediate evaluation with new config
            await self.hass.config_entries.async_reload(self.entry.entry_id)
        except Exception as err:
            _LOGGER.error("Error updating config: %s", err)
            raise


class HaBlindsAutomationSwitch(HaBlindsBaseSwitch):
    """Automation switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_automation"

    @property
    def name(self) -> str:
        return "Automation Enabled"

    @property
    def is_on(self) -> bool:
        return not bool(self.coordinator._runtime.paused_until)

    @property
    def icon(self) -> str:
        return "mdi:play" if self.is_on else "mdi:pause"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.coordinator.async_resume()

    async def async_turn_off(self, **kwargs):
        """Disable automation indefinitely until explicitly resumed."""
        await self.coordinator.async_pause(minutes=60 * 24 * 365)


class HaBlindsPrivacyHourSwitch(HaBlindsBaseSwitch):
    """Privacy hour feature switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_privacy_hour_enabled"

    @property
    def name(self) -> str:
        return "Privacy Hour Enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._cfg(CONF_ENABLE_PRIVACY_HOUR))

    @property
    def icon(self) -> str:
        return "mdi:moon-waning-crescent" if self.is_on else "mdi:moon-new"

    async def async_turn_on(self, **kwargs):
        """Turn on privacy hour."""
        await self._async_update_config(CONF_ENABLE_PRIVACY_HOUR, True)

    async def async_turn_off(self, **kwargs):
        """Turn off privacy hour."""
        await self._async_update_config(CONF_ENABLE_PRIVACY_HOUR, False)


class HaBlindsHighLuxProtectionSwitch(HaBlindsBaseSwitch):
    """High lux protection feature switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_high_lux_protection_enabled"

    @property
    def name(self) -> str:
        return "High Lux Protection Enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._cfg(CONF_ENABLE_HIGH_LUX_PROTECTION))

    @property
    def icon(self) -> str:
        return "mdi:brightness-7" if self.is_on else "mdi:brightness-6"

    async def async_turn_on(self, **kwargs):
        """Turn on high lux protection."""
        await self._async_update_config(CONF_ENABLE_HIGH_LUX_PROTECTION, True)

    async def async_turn_off(self, **kwargs):
        """Turn off high lux protection."""
        await self._async_update_config(CONF_ENABLE_HIGH_LUX_PROTECTION, False)


class HaBlindsHeatProtectionSwitch(HaBlindsBaseSwitch):
    """Heat protection feature switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_heat_protection_enabled"

    @property
    def name(self) -> str:
        return "Heat Protection Enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._cfg(CONF_ENABLE_HEAT_PROTECTION))

    @property
    def icon(self) -> str:
        return "mdi:thermometer" if self.is_on else "mdi:thermometer-off"

    async def async_turn_on(self, **kwargs):
        """Turn on heat protection."""
        await self._async_update_config(CONF_ENABLE_HEAT_PROTECTION, True)

    async def async_turn_off(self, **kwargs):
        """Turn off heat protection."""
        await self._async_update_config(CONF_ENABLE_HEAT_PROTECTION, False)


class HaBlindsLowLuxReopenSwitch(HaBlindsBaseSwitch):
    """Low lux reopen feature switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_low_lux_reopen_enabled"

    @property
    def name(self) -> str:
        return "Low Lux Reopen Enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._cfg(CONF_ENABLE_LOW_LUX_REOPEN))

    @property
    def icon(self) -> str:
        return "mdi:brightness-5" if self.is_on else "mdi:brightness-4"

    async def async_turn_on(self, **kwargs):
        """Turn on low lux reopen."""
        await self._async_update_config(CONF_ENABLE_LOW_LUX_REOPEN, True)

    async def async_turn_off(self, **kwargs):
        """Turn off low lux reopen."""
        await self._async_update_config(CONF_ENABLE_LOW_LUX_REOPEN, False)


class HaBlindsSunElevationTrackingSwitch(HaBlindsBaseSwitch):
    """Sun elevation tracking feature switch."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_sun_tracking_enabled"

    @property
    def name(self) -> str:
        return "Sun Elevation Tracking Enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._cfg(CONF_ENABLE_SUN_ELEVATION_TRACKING))

    @property
    def icon(self) -> str:
        return "mdi:sun-compass" if self.is_on else "mdi:sun-off"

    async def async_turn_on(self, **kwargs):
        """Turn on sun tracking."""
        await self._async_update_config(CONF_ENABLE_SUN_ELEVATION_TRACKING, True)

    async def async_turn_off(self, **kwargs):
        """Turn off sun tracking."""
        await self._async_update_config(CONF_ENABLE_SUN_ELEVATION_TRACKING, False)

