import unittest

from core.display_selection import monitor_contains_point, select_monitor


MONITORS = [
    {"left": -1920, "top": 0, "width": 5760, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    {"left": -1920, "top": 0, "width": 1920, "height": 1080},
]


class DisplaySelectionTests(unittest.TestCase):
    # -.-.-.-
    def test_point_selects_secondary_monitor(self):
        self.assertEqual(select_monitor(MONITORS, point=(2500, 400)), MONITORS[2])

    # -.-.-.-
    def test_negative_coordinates_select_left_monitor(self):
        self.assertTrue(monitor_contains_point(MONITORS[3], -900, 500))
        self.assertEqual(select_monitor(MONITORS, point=(-900, 500)), MONITORS[3])

    # -.-.-.-
    def test_all_hint_selects_virtual_desktop(self):
        self.assertEqual(select_monitor(MONITORS, hint="all"), MONITORS[0])

    # -.-.-.-
    def test_numeric_hint_selects_requested_monitor(self):
        self.assertEqual(select_monitor(MONITORS, hint=2), MONITORS[2])

    # -.-.-.-
    def test_invalid_hint_falls_back_to_first_real_monitor(self):
        self.assertEqual(select_monitor(MONITORS, hint="99"), MONITORS[1])


if __name__ == "__main__":
    unittest.main()
