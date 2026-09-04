import unittest

from core.window_geometry import (
    clip_rect_to_desktop,
    intersect_rect,
    monitor_index_for_rect,
    rect_area,
    region_savings_ratio,
)


MONITORS = [
    {"left": -1920, "top": 0, "width": 5760, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    {"left": -1920, "top": 0, "width": 1920, "height": 1080},
]


class WindowGeometryTests(unittest.TestCase):
    def test_intersection_preserves_negative_desktop_coordinates(self):
        window = {"left": -1700, "top": 100, "width": 1200, "height": 800}
        clipped = intersect_rect(window, MONITORS[3])

        self.assertEqual(
            clipped,
            {"left": -1700, "top": 100, "width": 1200, "height": 800},
        )
        self.assertEqual(monitor_index_for_rect(MONITORS, window), 3)

    def test_spanning_window_uses_monitor_with_largest_visible_area(self):
        window = {"left": 1500, "top": 100, "width": 1200, "height": 800}

        self.assertEqual(monitor_index_for_rect(MONITORS, window), 2)

    def test_window_is_clipped_to_virtual_desktop(self):
        window = {"left": -2500, "top": -100, "width": 1200, "height": 700}
        clipped = clip_rect_to_desktop(window, MONITORS)

        self.assertEqual(
            clipped,
            {"left": -1920, "top": 0, "width": 620, "height": 600},
        )

    def test_region_savings_reports_source_pixel_reduction(self):
        monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
        region = {"left": 200, "top": 100, "width": 960, "height": 540}

        self.assertEqual(rect_area(monitor), 2_073_600)
        self.assertAlmostEqual(region_savings_ratio(region, monitor), 0.75, places=3)


if __name__ == "__main__":
    unittest.main()
