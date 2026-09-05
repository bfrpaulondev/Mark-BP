import unittest
from unittest.mock import patch

from core.settings_postconditions import verify_settings_postcondition


class SettingsPostconditionTests(unittest.TestCase):
    @patch("core.settings_postconditions.platform.system", return_value="Windows")
    @patch("core.settings_postconditions.capture_settings_state", return_value={"volume_percent": 65, "muted": False})
    def test_volume_set_requires_readback_near_target(self, _state, _platform):
        result = verify_settings_postcondition(
            "volume_set",
            {"value": 65},
            before_state={"volume_percent": 20, "muted": False},
            delivered=True,
        )

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["expected_volume_percent"], 65)

    @patch("core.settings_postconditions.platform.system", return_value="Windows")
    @patch("core.settings_postconditions.capture_settings_state", return_value={"muted": False, "volume_percent": 30})
    def test_mute_does_not_verify_if_toggle_left_audio_unmuted(self, _state, _platform):
        result = verify_settings_postcondition(
            "mute",
            {},
            before_state={"muted": True, "volume_percent": 30},
            delivered=True,
        )

        self.assertFalse(result.verified)
        self.assertTrue(result.delivered)

    @patch("core.settings_postconditions.platform.system", return_value="Windows")
    @patch("core.settings_postconditions.capture_settings_state", return_value={"wifi_status": "Disabled", "wifi_enabled": False})
    def test_wifi_toggle_verifies_observed_state_change(self, _state, _platform):
        result = verify_settings_postcondition(
            "toggle_wifi",
            {},
            before_state={"wifi_status": "Up", "wifi_enabled": True},
            delivered=True,
        )

        self.assertTrue(result.can_claim_success)

    @patch("core.settings_postconditions.platform.system", return_value="Windows")
    @patch("core.settings_postconditions.capture_settings_state", return_value={})
    def test_unreadable_windows_state_stays_unverified(self, _state, _platform):
        result = verify_settings_postcondition(
            "dark_mode",
            {},
            before_state={"apps_dark": False, "system_dark": False},
            delivered=True,
        )

        self.assertFalse(result.verified)
        self.assertTrue(result.delivered)

    @patch("core.settings_postconditions.platform.system", return_value="Linux")
    def test_non_windows_setting_delivery_is_not_upgraded(self, _platform):
        result = verify_settings_postcondition(
            "volume_up",
            {},
            before_state={},
            delivered=True,
        )

        self.assertFalse(result.verified)
        self.assertTrue(result.delivered)


if __name__ == "__main__":
    unittest.main()
