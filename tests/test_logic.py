from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from custom_components.ha_blinds.logic import DecisionConfig, DecisionEngine, DecisionInputs


def _cfg() -> DecisionConfig:
    return DecisionConfig(
        window_azimuth=240,
        window_view_left=60,
        window_view_right=60,
        lux_close_summer=35000,
        lux_open_summer=20000,
        lux_close_winter=20000,
        lux_open_winter=12000,
        debounce_minutes=5,
        heat_start_hour=10,
        heat_end_hour=17,
        heat_position=20,
        temp_threshold=24.0,
        winter_privacy_hour=16,
        summer_privacy_hour=19,
        night_close_position=0,
    )


class TestDecisionEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DecisionEngine(_cfg())

    def test_privacy_hour_closes(self) -> None:
        now = datetime(2026, 12, 1, 17, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 220, 5, 10000, 21.0, 75, paused=False)
        )
        self.assertTrue(res.should_move)
        self.assertEqual(res.target_position, 0)  # night_close_position=0 in test config
        self.assertEqual(res.reason, "privacy_hour")

    def test_high_lux_debounce_closes(self) -> None:
        # Debounce state is tracked by the coordinator and passed via DecisionInputs.
        # Simulate coordinator having observed high lux for debounce_minutes already.
        start = datetime(2026, 7, 1, 13, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(
                start + timedelta(minutes=5), 230, 45, 40000, 26.0, 75,
                paused=False,
                high_lux_since=start,
            )
        )
        self.assertEqual(res.target_position, 0)
        self.assertEqual(res.reason, "direct_sun_high_lux")

    def test_sun_not_at_window_no_direct_close(self) -> None:
        now = datetime(2026, 7, 1, 13, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 80, 45, 80000, 28.0, 75, paused=False)
        )
        self.assertNotEqual(res.reason, "direct_sun_high_lux")

    def test_paused_makes_no_change(self) -> None:
        now = datetime(2026, 7, 1, 13, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 230, 45, 80000, 28.0, 75, paused=True)
        )
        self.assertFalse(res.should_move)
        self.assertEqual(res.reason, "paused")

    def test_sunset_closes_blinds(self) -> None:
        """Test that negative sun elevation triggers night_close."""
        # Use 03:00 so privacy_hour (summer threshold=19) is not yet active.
        now = datetime(2026, 7, 1, 3, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 230, -5, 5000, 22.0, 75, paused=False)
        )
        self.assertTrue(res.should_move)
        self.assertEqual(res.target_position, 0)  # night_close_position=0 in test config
        self.assertEqual(res.reason, "night_close")

    def test_night_stays_closed(self) -> None:
        """Test that blinds already at night_close_position do not move."""
        # Use 03:00 so privacy_hour (summer threshold=19) is not active.
        now = datetime(2026, 7, 1, 3, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 180, -20, 100, 18.0, 0, paused=False)
        )
        self.assertFalse(res.should_move)  # Already at night_close_position=0
        self.assertEqual(res.target_position, 0)
        self.assertEqual(res.reason, "night_close")
    
    def test_low_sun_closes(self) -> None:
        """Test that low elevation sun (eye level) closes blinds."""
        now = datetime(2026, 7, 1, 8, 0, 0)  # Early morning
        res = self.engine.evaluate(
            DecisionInputs(now, 230, 8, 5000, 18.0, 75, paused=False)
        )
        # Sun at 8° elevation = directly in eyes = close to 0%
        self.assertEqual(res.target_position, 0)
        self.assertEqual(res.reason, "sun_elevation_tracking")
    
    def test_high_sun_opens(self) -> None:
        """Test that high elevation sun (overhead) opens blinds via sun tracking."""
        # Use 09:00 (before heat_start_hour=10) and temp below threshold so
        # heat protection does not intercept before sun_elevation_tracking.
        now = datetime(2026, 7, 1, 9, 0, 0)
        res = self.engine.evaluate(
            DecisionInputs(now, 230, 70, 30000, 18.0, 50, paused=False)
        )
        # Sun at 70° elevation = overhead = open to 75%
        self.assertEqual(res.target_position, 75)
        self.assertEqual(res.reason, "sun_elevation_tracking")


    def test_pre_sunrise_keeps_closed(self) -> None:
        """When sunset_closing is enabled, blinds stay closed until sunrise."""
        cfg = DecisionConfig(
            **{**_cfg().__dict__,
               "enable_sunset_closing": True,
               "night_close_position": 0}
        )
        engine = DecisionEngine(cfg)
        now = datetime(2026, 7, 1, 4, 0, 0)          # After midnight, before sunrise
        sunrise = datetime(2026, 7, 1, 5, 30, 0)      # Sunrise at 05:30
        res = engine.evaluate(
            DecisionInputs(now, 180, 5, 500, 18.0, 0, paused=False, sunrise_time=sunrise)
        )
        self.assertFalse(res.should_move)   # Already at 0 (night_close_position)
        self.assertEqual(res.target_position, 0)
        self.assertEqual(res.reason, "pre_sunrise_closing")

    def test_after_sunrise_resumes_automation(self) -> None:
        """After sunrise, pre_sunrise_closing no longer applies."""
        cfg = DecisionConfig(
            **{**_cfg().__dict__,
               "enable_sunset_closing": True,
               "night_close_position": 0}
        )
        engine = DecisionEngine(cfg)
        now = datetime(2026, 7, 1, 6, 0, 0)           # After sunrise
        sunrise = datetime(2026, 7, 1, 5, 30, 0)       # Sunrise was at 05:30
        res = engine.evaluate(
            DecisionInputs(now, 230, 15, 5000, 18.0, 0, paused=False, sunrise_time=sunrise)
        )
        self.assertNotEqual(res.reason, "pre_sunrise_closing")


if __name__ == "__main__":
    unittest.main()

