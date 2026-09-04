import unittest
from pathlib import Path

from core.computer_use.contracts import FrameSnapshot, SessionState


class WindowScopedCaptureContractTests(unittest.TestCase):
    def test_window_crop_coordinates_still_map_to_virtual_desktop(self):
        frame = FrameSnapshot(
            sequence=1,
            timestamp=0.0,
            left=-1500,
            top=120,
            monitor_width=1000,
            monitor_height=800,
            image_width=500,
            image_height=400,
            monitor_index=3,
            change_score=1.0,
            jpeg_bytes=b"x",
            capture_scope="window",
            pixel_savings=0.55,
        )

        self.assertEqual(frame.to_screen_coordinates(250, 200), (-1000, 520))
        self.assertEqual(frame.capture_scope, "window")
        self.assertAlmostEqual(frame.pixel_savings, 0.55)

    def test_session_state_exposes_capture_scope_without_window_title_duplication(self):
        state = SessionState(
            capture_scope="window",
            capture_savings_pct=61,
        ).as_dict()

        self.assertEqual(state["capture_scope"], "window")
        self.assertEqual(state["capture_savings_pct"], 61)

    def test_realtime_capture_has_window_roi_fallback_contract(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "computer_use" / "capture.py").read_text(encoding="utf-8")
        session = (root / "core" / "computer_use" / "session.py").read_text(encoding="utf-8")

        self.assertIn('window_title: str = ""', source)
        self.assertIn("resolve_window_region", source)
        self.assertIn('capture_scope = "monitor"', source)
        self.assertIn('capture_scope = "window"', source)
        self.assertIn("window_title=self._state.target_window", session)
        self.assertIn("capture_savings_pct", session)


if __name__ == "__main__":
    unittest.main()
