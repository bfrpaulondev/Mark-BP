import os
import unittest
from unittest.mock import patch

from config.settings import AntonellaSettings


class LocalPerceptionSettingsTests(unittest.TestCase):
    def test_local_perception_is_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = AntonellaSettings()
        self.assertTrue(settings.computer_use_local_perception_enabled)

    def test_local_perception_can_be_disabled_explicitly(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = AntonellaSettings(computer_use_local_perception_enabled=False)
        self.assertFalse(settings.computer_use_local_perception_enabled)

    def test_environment_override_can_disable_local_perception(self):
        with patch.dict(
            os.environ,
            {"ANTONELLA_COMPUTER_USE_LOCAL_PERCEPTION_ENABLED": "false"},
            clear=True,
        ):
            settings = AntonellaSettings()
        self.assertFalse(settings.computer_use_local_perception_enabled)


if __name__ == "__main__":
    unittest.main()
