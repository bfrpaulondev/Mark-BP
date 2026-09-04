import unittest

from core.display_selection import (
    describe_monitors,
    monitor_contains_point,
    normalize_monitor_hint,
    select_monitor,
    selected_monitor_index,
)


MONITORS = [
    {"left": -1920, "top": 0, "width": 5760, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    {"left": -1920, "top": 0, "width": 1920, "height": 1080},
]


class DisplaySelectionTests(unittest.TestCase):
    def test_point_selects_secondary_monitor(self):
        self.assertEqual(select_monitor(MONITORS, point=(2500, 400)), MONITORS[2])

    def test_negative_coordinates_select_left_monitor(self):
        self.assertTrue(monitor_contains_point(MONITORS[3], -900, 500))
        self.assertEqual(select_monitor(MONITORS, point=(-900, 500)), MONITORS[3])

    def test_all_hint_selects_virtual_desktop(self):
        self.assertEqual(select_monitor(MONITORS, hint="all"), MONITORS[0])
        self.assertEqual(normalize_monitor_hint("combined"), "all")
        self.assertEqual(normalize_monitor_hint("todos os ecrãs"), "all")

    def test_numeric_and_natural_language_hints_select_requested_monitor(self):
        self.assertEqual(select_monitor(MONITORS, hint=2), MONITORS[2])
        self.assertEqual(select_monitor(MONITORS, hint="monitor 2"), MONITORS[2])
        self.assertEqual(select_monitor(MONITORS, hint="screen 3"), MONITORS[3])
        self.assertEqual(select_monitor(MONITORS, hint="ecrã 2"), MONITORS[2])
        self.assertEqual(select_monitor(MONITORS, hint="monitor dois"), MONITORS[2])
        self.assertEqual(select_monitor(MONITORS, hint="segundo monitor"), MONITORS[2])
        self.assertEqual(select_monitor(MONITORS, hint="terceiro ecrã"), MONITORS[3])

    def test_active_alias_uses_foreground_point(self):
        self.assertIsNone(normalize_monitor_hint("active"))
        self.assertIsNone(normalize_monitor_hint("ativo"))
        self.assertEqual(
            select_monitor(MONITORS, point=(-900, 500), hint="active"),
            MONITORS[3],
        )

    def test_invalid_hint_falls_back_to_first_real_monitor(self):
        self.assertEqual(select_monitor(MONITORS, hint="99"), MONITORS[1])

    def test_descriptions_exclude_combined_surface_and_mark_active(self):
        displays = describe_monitors(MONITORS, active_point=(2500, 400))

        self.assertEqual(len(displays), 3)
        self.assertEqual([item["index"] for item in displays], [1, 2, 3])
        self.assertFalse(displays[0]["active"])
        self.assertTrue(displays[1]["active"])
        self.assertEqual(selected_monitor_index(MONITORS, MONITORS[3]), 3)


if __name__ == "__main__":
    unittest.main()
