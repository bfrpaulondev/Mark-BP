import unittest
from pathlib import Path
from unittest.mock import patch

from core.computer_use.actuator import _frame_topology_is_current, execute_action
from core.computer_use.contracts import ComputerAction, FrameSnapshot


class ComputerUseDisplaySafetyTests(unittest.TestCase):
    def _frame(self, *, token: str = "topology-a") -> FrameSnapshot:
        return FrameSnapshot(
            sequence=4,
            timestamp=1.0,
            left=-1920,
            top=-1080,
            monitor_width=1920,
            monitor_height=1080,
            image_width=960,
            image_height=540,
            monitor_index=3,
            change_score=0.2,
            jpeg_bytes=b"frame",
            topology_token=token,
            dpi_x=144,
            dpi_y=144,
            scale_x=1.5,
            scale_y=1.5,
            monitor_device="DISPLAY3",
        )

    def test_physical_coordinate_mapping_does_not_double_apply_dpi_scale(self):
        frame = self._frame()

        x, y = frame.to_screen_coordinates(480, 270)

        self.assertEqual((x, y), (-960, -540))

    @patch("core.computer_use.actuator.current_topology_token", return_value="topology-b")
    def test_visual_action_is_rejected_when_frame_topology_is_stale(self, _token):
        frame = self._frame(token="topology-a")
        action = ComputerAction(action="click", x=300, y=200)

        result, reobserve = execute_action(action, frame)

        self.assertTrue(reobserve)
        self.assertIn("topology changed", result.lower())
        self.assertIn("not dispatched", result.lower())

    @patch("core.computer_use.actuator.current_topology_token", return_value="topology-a")
    def test_matching_topology_is_considered_current(self, _token):
        self.assertTrue(_frame_topology_is_current(self._frame(token="topology-a")))

    @patch("core.computer_use.actuator.current_topology_token", return_value="")
    def test_missing_live_token_preserves_legacy_fail_open_compatibility(self, _token):
        self.assertTrue(_frame_topology_is_current(self._frame(token="topology-a")))

    def test_capture_source_reopens_mss_and_pins_explicit_display_identity(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "computer_use" / "capture.py").read_text(encoding="utf-8")

        self.assertIn("display_topology_state", source)
        self.assertIn("strict_hint=explicit_monitor", source)
        self.assertIn("pinned_device", source)
        self.assertIn("sct.close()", source)
        self.assertIn("mss.mss()", source)
        self.assertIn("_invalidate_latest", source)
        self.assertIn("per_monitor_dpi_context", source)

    def test_window_geometry_is_resolved_inside_dpi_context(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "window_geometry.py").read_text(encoding="utf-8")

        self.assertIn("with per_monitor_dpi_context():", source)
        self.assertIn("GetWindowRect", source)


if __name__ == "__main__":
    unittest.main()
