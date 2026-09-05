import unittest
from unittest.mock import patch

from core.computer_use.contracts import FrameSnapshot
from core.computer_use.local_perception import LocalPerceptionPlanner


class LocalPerceptionGuardTests(unittest.TestCase):
    def _frame(self) -> FrameSnapshot:
        return FrameSnapshot(
            sequence=1,
            timestamp=1.0,
            left=0,
            top=0,
            monitor_width=1000,
            monitor_height=600,
            image_width=500,
            image_height=300,
            monitor_index=1,
            change_score=1.0,
            jpeg_bytes=b"frame",
            topology_token="topology",
            perception_digest="digest",
        )

    def test_generic_commit_buttons_never_take_local_route(self):
        planner = LocalPerceptionPlanner()
        with patch("actions.windows_ui_automation.windows_ui_automation") as inspect:
            for target in ("OK", "Yes", "Sim", "Continue", "Next", "Done"):
                with self.subTest(target=target):
                    self.assertIsNone(
                        planner.suggest(
                            objective=f'click "{target}"',
                            frame=self._frame(),
                            target_window="Example",
                        )
                    )
        inspect.assert_not_called()

    def test_external_privileged_and_write_targets_never_take_local_route(self):
        planner = LocalPerceptionPlanner()
        with patch("actions.windows_ui_automation.windows_ui_automation") as inspect:
            for target in (
                "Save",
                "Upload",
                "Download",
                "Sign in",
                "Log in",
                "Run",
                "Execute",
                "Install",
                "Place order",
            ):
                with self.subTest(target=target):
                    self.assertIsNone(
                        planner.suggest(
                            objective=f'click "{target}"',
                            frame=self._frame(),
                            target_window="Example",
                        )
                    )
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
