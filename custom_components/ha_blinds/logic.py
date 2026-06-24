"""Pure decision engine for HA Blinds.

This module stays Home-Assistant-independent so it can be unit-tested locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta



@dataclass
class DecisionConfig:
    window_azimuth: int
    window_view_left: int
    window_view_right: int
    lux_close_summer: float
    lux_close_winter: float
    debounce_minutes: int
    heat_start_hour: int
    heat_end_hour: int
    heat_position: int
    temp_threshold: float
    winter_privacy_hour: int
    summer_privacy_hour: int
    privacy_duration_minutes: int = 480
    night_close_position: int = 0
    daytime_open_position: int = 75
    # Feature toggles
    enable_heat_protection: bool = True
    enable_high_lux_protection: bool = True
    enable_privacy_hour: bool = True
    enable_sun_elevation_tracking: bool = True
    # Sunset/Sunrise feature
    enable_sunset_closing: bool = False
    sunrise_offset_minutes: int = 0
    sunset_offset_minutes: int = 0


@dataclass
class DecisionInputs:
    now: datetime
    sun_azimuth: float
    sun_elevation: float
    lux: float | None
    temperature: float | None
    current_position: int
    paused: bool
    sunrise_time: datetime | None = None
    sunset_time: datetime | None = None
    privacy_entered_at: datetime | None = None
    high_lux_since: datetime | None = None


@dataclass
class DecisionResult:
    should_move: bool
    target_position: int
    reason: str
    sun_at_window: bool


class DecisionEngine:
    """Evaluate desired slat position using sun/lux/season rules."""

    def __init__(self, config: DecisionConfig) -> None:
        self.config = config

    def evaluate(self, inputs: DecisionInputs) -> DecisionResult:
        is_winter = inputs.now.month in (11, 12, 1, 2, 3)
        sun_at_window = self._sun_at_window(inputs.sun_azimuth, inputs.sun_elevation)

        if inputs.paused:
            return DecisionResult(False, inputs.current_position, "paused", sun_at_window)

        # Sunset closing
        if self.config.enable_sunset_closing and inputs.sunset_time is not None:
            if inputs.now >= inputs.sunset_time:
                return self._result(inputs.current_position, self.config.night_close_position, "sunset_closing", sun_at_window)

        # Pre-sunrise: keep closed until sunrise + offset (sleep-in).
        # Guard: only fire after sunset_closing would have fired — prevents
        # pre_sunrise from jumping in during the sunset offset window.
        if self.config.enable_sunset_closing and inputs.sunrise_time is not None:
            if inputs.now < inputs.sunrise_time:
                if inputs.sunset_time is None or inputs.now >= inputs.sunset_time:
                    return self._result(inputs.current_position, self.config.night_close_position, "pre_sunrise_closing", sun_at_window)

        # Privacy hour
        if self.config.enable_privacy_hour and inputs.privacy_entered_at is not None:
            privacy_end_time = inputs.privacy_entered_at + timedelta(minutes=self.config.privacy_duration_minutes)
            if inputs.now < privacy_end_time:
                return self._result(inputs.current_position, self.config.night_close_position, "privacy_hour", sun_at_window)

        if self.config.enable_privacy_hour and inputs.privacy_entered_at is None:
            privacy_hour = self.config.winter_privacy_hour if is_winter else self.config.summer_privacy_hour
            if inputs.now.hour >= privacy_hour:
                return self._result(inputs.current_position, self.config.night_close_position, "privacy_hour", sun_at_window)

        # Night close (safety)
        if inputs.sun_elevation < 0:
            return self._result(inputs.current_position, self.config.night_close_position, "night_close", sun_at_window)

        # Daytime: branch on whether sun is in front of the window
        if sun_at_window:
            # High lux protection: direct sun glare → close
            if self.config.enable_high_lux_protection and inputs.high_lux_since is not None:
                if self._debounced(inputs.high_lux_since, inputs.now):
                    return self._result(inputs.current_position, 0, "direct_sun_high_lux", sun_at_window)

            # Heat protection: reduce opening during peak hours
            if (
                self.config.enable_heat_protection
                and not is_winter
                and self._hour_in_range(inputs.now.hour, self.config.heat_start_hour, self.config.heat_end_hour)
            ):
                return self._result(inputs.current_position, self.config.heat_position, "peak_heat_hours", sun_at_window)

            # Sun elevation tracking: adjust slat angle based on sun height
            if self.config.enable_sun_elevation_tracking:
                target = self._base_sun_target(inputs.sun_elevation)
                return self._result(inputs.current_position, target, "sun_elevation_tracking", sun_at_window)

            # Elevation tracking disabled — hold
            return DecisionResult(False, inputs.current_position, "sun_tracking_disabled", sun_at_window)

        # Sun not at window (morning / evening) — open to let in daylight
        return self._result(inputs.current_position, self.config.daytime_open_position, "daytime_open", sun_at_window)

    def _result(
        self,
        current_position: int,
        target_position: int,
        reason: str,
        sun_at_window: bool,
    ) -> DecisionResult:
        target = max(0, min(100, int(target_position)))
        return DecisionResult(abs(target - current_position) >= 2, target, reason, sun_at_window)

    def _debounced(self, since: datetime | None, now: datetime) -> bool:
        if since is None:
            return False
        return now - since >= timedelta(minutes=self.config.debounce_minutes)

    @staticmethod
    def _hour_in_range(hour: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def _sun_at_window(self, azimuth: float, elevation: float) -> bool:
        if elevation <= 0:
            return False
        left = (self.config.window_azimuth - self.config.window_view_left) % 360
        right = (self.config.window_azimuth + self.config.window_view_right) % 360
        if left <= right:
            return left <= azimuth <= right
        return azimuth >= left or azimuth <= right

    @staticmethod
    def _base_sun_target(elevation: float) -> int:
        """Slat position when sun is directly at the window.

        0% = closed, 75% = most open (horizontal slats).
        Low elevation = direct eye-level glare → close more.
        """
        if elevation < 10:
            return 0   # Very low sun — close completely
        if elevation < 25:
            return 50  # Low sun — half open
        return 75      # High sun — open
