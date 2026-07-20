"""Button entities for HA Blinds."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DAYTIME_OPEN_POSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PRESET_POSITIONS = [
    ("half", 50, "mdi:blinds", "Half Open (50%)"),
    ("slight", 25, "mdi:blinds", "Slightly Open (25%)"),
    ("close", 0, "mdi:blinds", "Close (0%)"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    from .coordinator import HaBlindsController

    coordinator: HaBlindsController = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HaBlindsEvaluateNowButton(coordinator, entry),
        HaBlindsDaytimeOpenButton(coordinator, entry),
        *[
            HaBlindsPresetPositionButton(coordinator, entry, key, position, icon, label)
            for key, position, icon, label in PRESET_POSITIONS
        ],
    ]

    async_add_entities(entities)


class HaBlindsBaseButton(ButtonEntity):
    """Base button."""

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


class HaBlindsEvaluateNowButton(HaBlindsBaseButton):
    """Evaluate now button."""

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_evaluate_now"

    @property
    def name(self) -> str:
        return "Evaluate Now"

    @property
    def icon(self) -> str:
        return "mdi:refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_evaluate_now()


class HaBlindsDaytimeOpenButton(HaBlindsBaseButton):
    """Open button that mirrors the configured daytime_open_position.

    Kept separate from the fixed presets below (half/slight/close) because
    this one has to track a user-configurable value, not a hardcoded one.
    """

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_position_open"

    @property
    def _position(self) -> int:
        return self.coordinator._cfg_int(CONF_DAYTIME_OPEN_POSITION)

    @property
    def name(self) -> str:
        return f"Open ({self._position}%)"

    @property
    def icon(self) -> str:
        return "mdi:blinds-open"

    async def async_press(self) -> None:
        await self.coordinator.async_set_position(self._position)


class HaBlindsPresetPositionButton(HaBlindsBaseButton):
    """Button to set covers to a preset position and pause automation."""

    def __init__(self, coordinator, entry: ConfigEntry, key: str, position: int, icon: str, label: str):
        super().__init__(coordinator, entry)
        self._key = key
        self._position = position
        self._icon = icon
        self._label = label

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_position_{self._key}"

    @property
    def name(self) -> str:
        return self._label

    @property
    def icon(self) -> str:
        return self._icon

    async def async_press(self) -> None:
        await self.coordinator.async_set_position(self._position)
