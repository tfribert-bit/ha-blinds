"""Config flow for HA Blinds."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector as sel

from .const import (
    CONF_COVER_ENTITIES,
    CONF_COVER_ENTITY,
    CONF_DEBOUNCE_MINUTES,
    CONF_ENABLE_HEAT_PROTECTION,
    CONF_ENABLE_HIGH_LUX_PROTECTION,
    CONF_ENABLE_PRIVACY_HOUR,
    CONF_ENABLE_SUN_ELEVATION_TRACKING,
    CONF_ENABLE_SUNSET_CLOSING,
    CONF_HEAT_END_HOUR,
    CONF_HEAT_POSITION,
    CONF_HEAT_START_HOUR,
    CONF_LUX_CLOSE_SUMMER,
    CONF_LUX_CLOSE_WINTER,
    CONF_LUX_SENSOR,
    CONF_DAYTIME_OPEN_POSITION,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MAX_STEP_PER_TICK,
    CONF_NIGHT_CLOSE_POSITION,
    CONF_PRIVACY_DURATION_MINUTES,
    CONF_SUMMER_PRIVACY_HOUR,
    CONF_SUNRISE_OFFSET_MINUTES,
    CONF_SUNSET_OFFSET_MINUTES,
    CONF_TEMP_SENSOR,
    CONF_TEMP_THRESHOLD,
    CONF_TICK_MINUTES,
    CONF_WINDOW_AZIMUTH,
    CONF_WINDOW_VIEW_LEFT,
    CONF_WINDOW_VIEW_RIGHT,
    CONF_WINTER_PRIVACY_HOUR,
    CONF_ZIGBEE_DELAY_SECONDS,
    DEFAULTS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _convert_time_inputs(user_input: dict[str, Any]) -> None:
    """Convert HH:MM time strings to integer hours in-place."""
    for time_key in [CONF_HEAT_START_HOUR, CONF_HEAT_END_HOUR, CONF_WINTER_PRIVACY_HOUR, CONF_SUMMER_PRIVACY_HOUR]:
        if time_key in user_input:
            user_input[time_key] = _coerce_hour_value(user_input[time_key])


def _coerce_hour_value(value: Any) -> int:
    """Coerce hour selector output to an integer hour (0-23)."""
    if isinstance(value, int):
        hour = value
    elif isinstance(value, str):
        hour_str = value.split(":", 1)[0].strip()
        hour = int(hour_str)
    else:
        raise ValueError("Hour value must be int or HH:MM string")

    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    return hour


def _convert_night_close_position(user_input: dict[str, Any]) -> None:
    """Convert night close position string to integer in-place."""
    if CONF_NIGHT_CLOSE_POSITION in user_input:
        user_input[CONF_NIGHT_CLOSE_POSITION] = _coerce_night_close_position(user_input[CONF_NIGHT_CLOSE_POSITION])


def _coerce_night_close_position(value: Any) -> int:
    """Coerce night close selector output to supported integer values."""
    if isinstance(value, int):
        position = value
    elif isinstance(value, str):
        position = int(value.split()[0])
    else:
        raise ValueError("Night close position must be int or selector string")

    if position not in (0, 100):
        raise ValueError("Night close position must be 0 or 100")
    return position


def _hour_default_label(value: Any, fallback: int) -> str:
    """Return a resilient HH:MM label for selector defaults."""
    try:
        hour = _coerce_hour_value(value)
    except (TypeError, ValueError):
        hour = int(fallback)
    return f"{hour:02d}:00"


def _night_position_default_label(value: Any, fallback: int) -> str:
    """Return a resilient selector label for night close position."""
    try:
        position = _coerce_night_close_position(value)
    except (TypeError, ValueError):
        position = int(fallback)
    return "0 (Closed)" if position == 0 else "100 (Privacy Mode)"


def _coerce_int_default(value: Any, fallback: int) -> int:
    """Coerce legacy numeric defaults while tolerating old string formats."""
    try:
        if isinstance(value, bool):
            raise ValueError("bool is not valid int option")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            raw = value.strip()
            if ":" in raw:
                raw = raw.split(":", 1)[0].strip()
            if " " in raw:
                raw = raw.split(" ", 1)[0].strip()
            return int(float(raw))
    except (TypeError, ValueError):
        pass
    return int(fallback)


def _coerce_float_default(value: Any, fallback: float) -> float:
    """Coerce legacy float defaults while tolerating old string formats."""
    try:
        if isinstance(value, bool):
            raise ValueError("bool is not valid float option")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
    except (TypeError, ValueError):
        pass
    return float(fallback)


def _coerce_bool_default(value: Any, fallback: bool) -> bool:
    """Coerce legacy boolean defaults from bool/int/string values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(fallback)


def _sanitize_option_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted option values so options forms can always render."""
    sanitized = dict(defaults)

    int_keys = (
        CONF_LUX_CLOSE_SUMMER,
        CONF_LUX_CLOSE_WINTER,
        CONF_DEBOUNCE_MINUTES,
        CONF_DAYTIME_OPEN_POSITION,
        CONF_TICK_MINUTES,
        CONF_MAX_STEP_PER_TICK,
        CONF_HEAT_POSITION,
        CONF_PRIVACY_DURATION_MINUTES,
        CONF_MANUAL_OVERRIDE_MINUTES,
        CONF_ZIGBEE_DELAY_SECONDS,
        CONF_SUNSET_OFFSET_MINUTES,
        CONF_SUNRISE_OFFSET_MINUTES,
    )
    for key in int_keys:
        sanitized[key] = _coerce_int_default(sanitized.get(key), int(DEFAULTS[key]))

    sanitized[CONF_TEMP_THRESHOLD] = _coerce_float_default(
        sanitized.get(CONF_TEMP_THRESHOLD),
        float(DEFAULTS[CONF_TEMP_THRESHOLD]),
    )

    bool_keys = (
        CONF_ENABLE_SUNSET_CLOSING,
        CONF_ENABLE_PRIVACY_HOUR,
        CONF_ENABLE_HIGH_LUX_PROTECTION,
        CONF_ENABLE_HEAT_PROTECTION,
        CONF_ENABLE_SUN_ELEVATION_TRACKING,
    )
    for key in bool_keys:
        sanitized[key] = _coerce_bool_default(sanitized.get(key), bool(DEFAULTS[key]))

    try:
        sanitized[CONF_HEAT_START_HOUR] = _coerce_hour_value(sanitized.get(CONF_HEAT_START_HOUR))
    except (TypeError, ValueError):
        sanitized[CONF_HEAT_START_HOUR] = int(DEFAULTS[CONF_HEAT_START_HOUR])
    try:
        sanitized[CONF_HEAT_END_HOUR] = _coerce_hour_value(sanitized.get(CONF_HEAT_END_HOUR))
    except (TypeError, ValueError):
        sanitized[CONF_HEAT_END_HOUR] = int(DEFAULTS[CONF_HEAT_END_HOUR])
    try:
        sanitized[CONF_WINTER_PRIVACY_HOUR] = _coerce_hour_value(sanitized.get(CONF_WINTER_PRIVACY_HOUR))
    except (TypeError, ValueError):
        sanitized[CONF_WINTER_PRIVACY_HOUR] = int(DEFAULTS[CONF_WINTER_PRIVACY_HOUR])
    try:
        sanitized[CONF_SUMMER_PRIVACY_HOUR] = _coerce_hour_value(sanitized.get(CONF_SUMMER_PRIVACY_HOUR))
    except (TypeError, ValueError):
        sanitized[CONF_SUMMER_PRIVACY_HOUR] = int(DEFAULTS[CONF_SUMMER_PRIVACY_HOUR])

    try:
        sanitized[CONF_NIGHT_CLOSE_POSITION] = _coerce_night_close_position(
            sanitized.get(CONF_NIGHT_CLOSE_POSITION)
        )
    except (TypeError, ValueError):
        sanitized[CONF_NIGHT_CLOSE_POSITION] = int(DEFAULTS[CONF_NIGHT_CLOSE_POSITION])

    return sanitized


def _entry_schema(defaults: dict[str, Any]) -> vol.Schema:
    schema = {
        vol.Required(CONF_COVER_ENTITY): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="cover")
        ),
        vol.Optional(CONF_COVER_ENTITIES, default=[]): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="cover", multiple=True)
        ),
        vol.Required(CONF_LUX_SENSOR): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="sensor", device_class="illuminance")
        ),
        vol.Optional(CONF_TEMP_SENSOR): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        vol.Required(
            CONF_WINDOW_AZIMUTH,
            default=int(defaults.get(CONF_WINDOW_AZIMUTH, DEFAULTS[CONF_WINDOW_AZIMUTH])),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=359)),
        vol.Required(
            CONF_WINDOW_VIEW_LEFT,
            default=int(defaults.get(CONF_WINDOW_VIEW_LEFT, DEFAULTS[CONF_WINDOW_VIEW_LEFT])),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
        vol.Required(
            CONF_WINDOW_VIEW_RIGHT,
            default=int(defaults.get(CONF_WINDOW_VIEW_RIGHT, DEFAULTS[CONF_WINDOW_VIEW_RIGHT])),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
    }

    if CONF_COVER_ENTITY in defaults:
        schema[vol.Required(CONF_COVER_ENTITY, default=defaults[CONF_COVER_ENTITY])] = schema.pop(vol.Required(CONF_COVER_ENTITY))
    if CONF_COVER_ENTITIES in defaults:
        schema[vol.Optional(CONF_COVER_ENTITIES, default=defaults[CONF_COVER_ENTITIES])] = schema.pop(vol.Optional(CONF_COVER_ENTITIES, default=[]))
    if CONF_LUX_SENSOR in defaults:
        schema[vol.Required(CONF_LUX_SENSOR, default=defaults[CONF_LUX_SENSOR])] = schema.pop(vol.Required(CONF_LUX_SENSOR))
    if CONF_TEMP_SENSOR in defaults:
        schema[vol.Optional(CONF_TEMP_SENSOR, description={"suggested_value": defaults[CONF_TEMP_SENSOR]})] = schema.pop(vol.Optional(CONF_TEMP_SENSOR))

    return vol.Schema(schema)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    defaults = _sanitize_option_defaults({**DEFAULTS, **defaults})
    return vol.Schema(
        {
            vol.Required(CONF_LUX_CLOSE_SUMMER, default=defaults[CONF_LUX_CLOSE_SUMMER]): vol.All(vol.Coerce(int), vol.Range(min=1000, max=120000)),
            vol.Required(CONF_LUX_CLOSE_WINTER, default=defaults[CONF_LUX_CLOSE_WINTER]): vol.All(vol.Coerce(int), vol.Range(min=500, max=120000)),
            vol.Required(CONF_DEBOUNCE_MINUTES, default=defaults[CONF_DEBOUNCE_MINUTES]): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(CONF_TICK_MINUTES, default=defaults[CONF_TICK_MINUTES]): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(CONF_MAX_STEP_PER_TICK, default=defaults[CONF_MAX_STEP_PER_TICK]): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            vol.Required(CONF_HEAT_START_HOUR, default=_hour_default_label(defaults.get(CONF_HEAT_START_HOUR, DEFAULTS[CONF_HEAT_START_HOUR]), DEFAULTS[CONF_HEAT_START_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_HEAT_END_HOUR, default=_hour_default_label(defaults.get(CONF_HEAT_END_HOUR, DEFAULTS[CONF_HEAT_END_HOUR]), DEFAULTS[CONF_HEAT_END_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_HEAT_POSITION, default=defaults[CONF_HEAT_POSITION]): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Required(CONF_TEMP_THRESHOLD, default=defaults[CONF_TEMP_THRESHOLD]): vol.All(vol.Coerce(float), vol.Range(min=10, max=40)),
            vol.Required(CONF_WINTER_PRIVACY_HOUR, default=_hour_default_label(defaults.get(CONF_WINTER_PRIVACY_HOUR, DEFAULTS[CONF_WINTER_PRIVACY_HOUR]), DEFAULTS[CONF_WINTER_PRIVACY_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_SUMMER_PRIVACY_HOUR, default=_hour_default_label(defaults.get(CONF_SUMMER_PRIVACY_HOUR, DEFAULTS[CONF_SUMMER_PRIVACY_HOUR]), DEFAULTS[CONF_SUMMER_PRIVACY_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_PRIVACY_DURATION_MINUTES, default=defaults[CONF_PRIVACY_DURATION_MINUTES]): vol.All(vol.Coerce(int), vol.Range(min=60, max=1440)),
            vol.Required(CONF_MANUAL_OVERRIDE_MINUTES, default=defaults[CONF_MANUAL_OVERRIDE_MINUTES]): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
            vol.Required(
                CONF_NIGHT_CLOSE_POSITION,
                default=_night_position_default_label(
                    defaults.get(CONF_NIGHT_CLOSE_POSITION, DEFAULTS[CONF_NIGHT_CLOSE_POSITION]),
                    DEFAULTS[CONF_NIGHT_CLOSE_POSITION],
                ),
            ): sel.SelectSelector(sel.SelectSelectorConfig(options=["0 (Closed)", "100 (Privacy Mode)"], mode="dropdown")),
            vol.Required(CONF_ZIGBEE_DELAY_SECONDS, default=defaults[CONF_ZIGBEE_DELAY_SECONDS]): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
            # Sunset/Sunrise feature - uses sun.sun entity
            vol.Required(CONF_ENABLE_SUNSET_CLOSING, default=defaults[CONF_ENABLE_SUNSET_CLOSING]): sel.BooleanSelector(),
            vol.Required(CONF_SUNSET_OFFSET_MINUTES, default=defaults[CONF_SUNSET_OFFSET_MINUTES]): sel.NumberSelector(sel.NumberSelectorConfig(min=-120, max=120, step=1, mode=sel.NumberSelectorMode.BOX)),
            vol.Required(CONF_SUNRISE_OFFSET_MINUTES, default=defaults[CONF_SUNRISE_OFFSET_MINUTES]): sel.NumberSelector(sel.NumberSelectorConfig(min=-120, max=120, step=1, mode=sel.NumberSelectorMode.BOX)),
            # Feature toggles
            vol.Required(CONF_ENABLE_PRIVACY_HOUR, default=defaults[CONF_ENABLE_PRIVACY_HOUR]): sel.BooleanSelector(),
            vol.Required(CONF_ENABLE_HIGH_LUX_PROTECTION, default=defaults[CONF_ENABLE_HIGH_LUX_PROTECTION]): sel.BooleanSelector(),
            vol.Required(CONF_ENABLE_HEAT_PROTECTION, default=defaults[CONF_ENABLE_HEAT_PROTECTION]): sel.BooleanSelector(),
            vol.Required(CONF_ENABLE_SUN_ELEVATION_TRACKING, default=defaults[CONF_ENABLE_SUN_ELEVATION_TRACKING]): sel.BooleanSelector(),
        }
    )


class HaBlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Blinds."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_COVER_ENTITY])
            self._abort_if_unique_id_configured()
            self.context["user_data"] = user_input
            return await self.async_step_options()

        errors = {}
        return self.async_show_form(
            step_id="user",
            data_schema=_entry_schema({}),
            errors=errors,
            description_placeholders={
                "setup_info": "Select your blind cover entity, a lux sensor, and define your window orientation.",
            },
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            data = dict(self.context.get("user_data", {}))
            if not data:
                return self.async_abort(reason="unknown")
            if not user_input.get(CONF_TEMP_SENSOR):
                user_input.pop(CONF_TEMP_SENSOR, None)
            # Convert time strings back to integers
            _convert_time_inputs(user_input)
            _convert_night_close_position(user_input)
            return self.async_create_entry(
                title=f"HA Blinds ({data[CONF_COVER_ENTITY]})",
                data=data,
                options=user_input,
            )

        return self.async_show_form(step_id="options", data_schema=_options_schema(DEFAULTS), errors={})

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Reconfigure step - just for updating entity IDs, not for editing settings."""
        config_entry = self._get_reconfigure_entry()
        
        if user_input is not None:
            if not user_input.get(CONF_TEMP_SENSOR):
                user_input.pop(CONF_TEMP_SENSOR, None)
            
            # Check for unique ID collision if cover entity changed
            old_cover = config_entry.data.get(CONF_COVER_ENTITY)
            new_cover = user_input.get(CONF_COVER_ENTITY)
            if new_cover and new_cover != old_cover:
                await self.async_set_unique_id(new_cover)
                self._abort_if_unique_id_configured()
            
            # Update only entity and window orientation data
            updated_data = {
                **config_entry.data,
                CONF_COVER_ENTITY: user_input.get(CONF_COVER_ENTITY, config_entry.data.get(CONF_COVER_ENTITY)),
                CONF_COVER_ENTITIES: user_input.get(CONF_COVER_ENTITIES, config_entry.data.get(CONF_COVER_ENTITIES, [])),
                CONF_LUX_SENSOR: user_input.get(CONF_LUX_SENSOR, config_entry.data.get(CONF_LUX_SENSOR)),
                CONF_TEMP_SENSOR: user_input.get(CONF_TEMP_SENSOR, config_entry.data.get(CONF_TEMP_SENSOR)),
                CONF_WINDOW_AZIMUTH: user_input.get(CONF_WINDOW_AZIMUTH, config_entry.data.get(CONF_WINDOW_AZIMUTH)),
                CONF_WINDOW_VIEW_LEFT: user_input.get(CONF_WINDOW_VIEW_LEFT, config_entry.data.get(CONF_WINDOW_VIEW_LEFT)),
                CONF_WINDOW_VIEW_RIGHT: user_input.get(CONF_WINDOW_VIEW_RIGHT, config_entry.data.get(CONF_WINDOW_VIEW_RIGHT)),
            }
            update_kwargs: dict[str, Any] = {
                "data_updates": updated_data,
                "reason": "reconfigure_successful",
            }
            if new_cover and new_cover != old_cover:
                update_kwargs["unique_id"] = new_cover
            return self.async_update_reload_and_abort(
                config_entry,
                **update_kwargs,
            )
        
        defaults = config_entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_entry_schema(defaults),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return HaBlindsOptionsFlow()


class HaBlindsOptionsFlow(config_entries.OptionsFlow):
    """Options flow for HA Blinds."""

    def _entry(self) -> config_entries.ConfigEntry:
        """Return active config entry for this options flow."""
        return self.config_entry

    def _defaults(self) -> dict[str, Any]:
        """Return merged defaults with persisted values taking precedence."""
        try:
            entry = self._entry()
            merged: dict[str, Any] = dict(DEFAULTS)
            merged.update(dict(entry.data))
            merged.update(dict(entry.options))
            return _sanitize_option_defaults(merged)
        except vol.Invalid:
            _LOGGER.exception("Unable to resolve config entry; falling back to hard defaults")
            return dict(DEFAULTS)
        except Exception:
            _LOGGER.exception("Failed to build option defaults; falling back to hard defaults")
            return dict(DEFAULTS)

    def _show_schema_form(
        self,
        step_id: str,
        schema_dict: dict[Any, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ):
        """Render a form while preventing schema build crashes from bubbling up."""
        try:
            schema = vol.Schema(schema_dict)
        except Exception:
            _LOGGER.exception("Failed to build schema for options step '%s'", step_id)
            errors = {**errors, "base": "unknown"}
            schema = vol.Schema({})
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    def _normalized_options(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Normalize selector outputs and keep option types stable."""
        cleaned = dict(user_input)
        if not cleaned.get(CONF_TEMP_SENSOR):
            cleaned.pop(CONF_TEMP_SENSOR, None)
        try:
            _convert_time_inputs(cleaned)
            _convert_night_close_position(cleaned)
        except (TypeError, ValueError) as err:
            raise vol.Invalid("Invalid option value") from err
        return cleaned

    def _current_options(self) -> dict[str, Any]:
        """Return persisted options as a dict, tolerating malformed storage."""
        return dict(self._entry().options)

    def _save_options_entry(self, user_input: dict[str, Any]):
        """Merge and persist updated options."""
        try:
            entry = self._entry()
            options = self._current_options()
            options.update(self._normalized_options(user_input))
            _LOGGER.debug("Saving options for entry %s: keys=%s", entry.entry_id, sorted(options.keys()))
            return self.async_create_entry(title="", data=options)
        except Exception as err:
            _LOGGER.exception("Failed to save options entry")
            raise vol.Invalid("Invalid option value") from err

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["thresholds", "timing", "sunset", "features"],
            description_placeholders={
                "info": "Choose what to configure. Use Reconfigure from the integration menu for entity changes.",
            },
        )


    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None):
        """Threshold configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return self._save_options_entry(user_input)
            except Exception:
                _LOGGER.exception("Invalid threshold options payload")
                errors["base"] = "unknown"

        defaults = self._defaults()
        schema_dict = {
            vol.Required(
                CONF_LUX_CLOSE_SUMMER,
                default=_coerce_int_default(defaults.get(CONF_LUX_CLOSE_SUMMER), int(DEFAULTS[CONF_LUX_CLOSE_SUMMER])),
            ): vol.All(vol.Coerce(int), vol.Range(min=1000, max=120000)),
            vol.Required(
                CONF_LUX_CLOSE_WINTER,
                default=_coerce_int_default(defaults.get(CONF_LUX_CLOSE_WINTER), int(DEFAULTS[CONF_LUX_CLOSE_WINTER])),
            ): vol.All(vol.Coerce(int), vol.Range(min=500, max=120000)),
            vol.Required(CONF_HEAT_START_HOUR, default=_hour_default_label(defaults.get(CONF_HEAT_START_HOUR, DEFAULTS[CONF_HEAT_START_HOUR]), DEFAULTS[CONF_HEAT_START_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_HEAT_END_HOUR, default=_hour_default_label(defaults.get(CONF_HEAT_END_HOUR, DEFAULTS[CONF_HEAT_END_HOUR]), DEFAULTS[CONF_HEAT_END_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(
                CONF_HEAT_POSITION,
                default=_coerce_int_default(defaults.get(CONF_HEAT_POSITION), int(DEFAULTS[CONF_HEAT_POSITION])),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Required(
                CONF_TEMP_THRESHOLD,
                default=_coerce_float_default(defaults.get(CONF_TEMP_THRESHOLD), float(DEFAULTS[CONF_TEMP_THRESHOLD])),
            ): vol.All(vol.Coerce(float), vol.Range(min=10, max=40)),
            vol.Required(CONF_WINTER_PRIVACY_HOUR, default=_hour_default_label(defaults.get(CONF_WINTER_PRIVACY_HOUR, DEFAULTS[CONF_WINTER_PRIVACY_HOUR]), DEFAULTS[CONF_WINTER_PRIVACY_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_SUMMER_PRIVACY_HOUR, default=_hour_default_label(defaults.get(CONF_SUMMER_PRIVACY_HOUR, DEFAULTS[CONF_SUMMER_PRIVACY_HOUR]), DEFAULTS[CONF_SUMMER_PRIVACY_HOUR])): sel.SelectSelector(sel.SelectSelectorConfig(options=[f"{i:02d}:00" for i in range(24)], mode="dropdown")),
            vol.Required(CONF_NIGHT_CLOSE_POSITION, default=_night_position_default_label(defaults.get(CONF_NIGHT_CLOSE_POSITION, DEFAULTS[CONF_NIGHT_CLOSE_POSITION]), DEFAULTS[CONF_NIGHT_CLOSE_POSITION])): sel.SelectSelector(sel.SelectSelectorConfig(options=["0 (Closed)", "100 (Privacy Mode)"], mode="dropdown")),
            vol.Required(
                CONF_DAYTIME_OPEN_POSITION,
                default=_coerce_int_default(defaults.get(CONF_DAYTIME_OPEN_POSITION), int(DEFAULTS[CONF_DAYTIME_OPEN_POSITION])),
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=100)),
        }
        return self._show_schema_form(
            step_id="thresholds",
            schema_dict=schema_dict,
            errors=errors,
            description_placeholders={
                "help": "Adjust lux thresholds, heat protection, and privacy hours",
            },
        )

    async def async_step_timing(self, user_input: dict[str, Any] | None = None):
        """Timing configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return self._save_options_entry(user_input)
            except Exception:
                _LOGGER.exception("Invalid timing options payload")
                errors["base"] = "unknown"

        defaults = self._defaults()
        schema_dict = {
            vol.Required(
                CONF_TICK_MINUTES,
                default=_coerce_int_default(defaults.get(CONF_TICK_MINUTES), int(DEFAULTS[CONF_TICK_MINUTES])),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(
                CONF_MAX_STEP_PER_TICK,
                default=_coerce_int_default(defaults.get(CONF_MAX_STEP_PER_TICK), int(DEFAULTS[CONF_MAX_STEP_PER_TICK])),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            vol.Required(
                CONF_DEBOUNCE_MINUTES,
                default=_coerce_int_default(defaults.get(CONF_DEBOUNCE_MINUTES), int(DEFAULTS[CONF_DEBOUNCE_MINUTES])),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(
                CONF_MANUAL_OVERRIDE_MINUTES,
                default=_coerce_int_default(
                    defaults.get(CONF_MANUAL_OVERRIDE_MINUTES),
                    int(DEFAULTS[CONF_MANUAL_OVERRIDE_MINUTES]),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
        }
        return self._show_schema_form(
            step_id="timing",
            schema_dict=schema_dict,
            errors=errors,
            description_placeholders={
                "help": "Adjust check frequency, movement speed, and response timing",
            },
        )

    async def async_step_sunset(self, user_input: dict[str, Any] | None = None):
        """Sunset/Sunrise configuration - uses built-in sun.sun entity."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return self._save_options_entry(user_input)
            except Exception:
                _LOGGER.exception("Invalid sunset options payload")
                errors["base"] = "unknown"

        defaults = self._defaults()
        schema_dict = {
            vol.Required(
                CONF_ENABLE_SUNSET_CLOSING,
                default=_coerce_bool_default(
                    defaults.get(CONF_ENABLE_SUNSET_CLOSING),
                    bool(DEFAULTS[CONF_ENABLE_SUNSET_CLOSING]),
                ),
            ): sel.BooleanSelector(),
            vol.Required(
                CONF_SUNSET_OFFSET_MINUTES,
                default=_coerce_int_default(defaults.get(CONF_SUNSET_OFFSET_MINUTES), int(DEFAULTS[CONF_SUNSET_OFFSET_MINUTES])),
            ): sel.NumberSelector(sel.NumberSelectorConfig(min=-120, max=120, step=1, mode=sel.NumberSelectorMode.BOX)),
            vol.Required(
                CONF_SUNRISE_OFFSET_MINUTES,
                default=_coerce_int_default(defaults.get(CONF_SUNRISE_OFFSET_MINUTES), int(DEFAULTS[CONF_SUNRISE_OFFSET_MINUTES])),
            ): sel.NumberSelector(sel.NumberSelectorConfig(min=-120, max=120, step=1, mode=sel.NumberSelectorMode.BOX)),
        }
        return self._show_schema_form(
            step_id="sunset",
            schema_dict=schema_dict,
            errors=errors,
            description_placeholders={
                "help": "Configure sunset/sunrise offsets. Uses the built-in sun.sun entity (automatically detected).",
            },
        )

    async def async_step_features(self, user_input: dict[str, Any] | None = None):
        """Feature toggles configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return self._save_options_entry(user_input)
            except Exception:
                _LOGGER.exception("Invalid feature toggle payload")
                errors["base"] = "unknown"

        defaults = self._defaults()
        schema_dict = {
            vol.Required(
                CONF_ENABLE_PRIVACY_HOUR,
                default=_coerce_bool_default(defaults.get(CONF_ENABLE_PRIVACY_HOUR), bool(DEFAULTS[CONF_ENABLE_PRIVACY_HOUR])),
            ): sel.BooleanSelector(),
            vol.Required(
                CONF_ENABLE_HIGH_LUX_PROTECTION,
                default=_coerce_bool_default(
                    defaults.get(CONF_ENABLE_HIGH_LUX_PROTECTION),
                    bool(DEFAULTS[CONF_ENABLE_HIGH_LUX_PROTECTION]),
                ),
            ): sel.BooleanSelector(),
            vol.Required(
                CONF_ENABLE_HEAT_PROTECTION,
                default=_coerce_bool_default(defaults.get(CONF_ENABLE_HEAT_PROTECTION), bool(DEFAULTS[CONF_ENABLE_HEAT_PROTECTION])),
            ): sel.BooleanSelector(),
            vol.Required(
                CONF_ENABLE_SUN_ELEVATION_TRACKING,
                default=_coerce_bool_default(
                    defaults.get(CONF_ENABLE_SUN_ELEVATION_TRACKING),
                    bool(DEFAULTS[CONF_ENABLE_SUN_ELEVATION_TRACKING]),
                ),
            ): sel.BooleanSelector(),
        }
        return self._show_schema_form(
            step_id="features",
            schema_dict=schema_dict,
            errors=errors,
            description_placeholders={
                "help": "Enable or disable specific automation rules",
            },
        )


