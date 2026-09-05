import unittest

from core.display_selection import select_monitor
from core.display_topology import (
    describe_dpi_metadata,
    match_monitor_metadata,
    topology_token,
)


class DisplayTopologyTests(unittest.TestCase):
    def setUp(self):
        self.monitors = [
            {"left": -1920, "top": -1080, "width": 4480, "height": 2520},
            {"left": 0, "top": 0, "width": 2560, "height": 1440},
            {"left": -1920, "top": 0, "width": 1920, "height": 1080},
            {"left": 0, "top": -1080, "width": 1920, "height": 1080},
        ]
        self.metadata = [
            {
                "left": 0,
                "top": -1080,
                "width": 1920,
                "height": 1080,
                "device": "DISPLAY3",
                "primary": False,
                "dpi_x": 192,
                "dpi_y": 192,
                "scale_x": 2.0,
                "scale_y": 2.0,
            },
            {
                "left": -1920,
                "top": 0,
                "width": 1920,
                "height": 1080,
                "device": "DISPLAY2",
                "primary": False,
                "dpi_x": 120,
                "dpi_y": 120,
                "scale_x": 1.25,
                "scale_y": 1.25,
            },
            {
                "left": 0,
                "top": 0,
                "width": 2560,
                "height": 1440,
                "device": "DISPLAY1",
                "primary": True,
                "dpi_x": 144,
                "dpi_y": 144,
                "scale_x": 1.5,
                "scale_y": 1.5,
            },
        ]

    def test_metadata_matches_physical_geometry_not_enumeration_order(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)

        self.assertEqual(matched[1]["device"], "DISPLAY1")
        self.assertEqual(matched[2]["device"], "DISPLAY2")
        self.assertEqual(matched[3]["device"], "DISPLAY3")
        self.assertTrue(matched[1]["primary"])

    def test_dpi_scale_metadata_supports_common_windows_scales(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)

        self.assertEqual(describe_dpi_metadata(2, matched)["scale_x"], 1.25)
        self.assertEqual(describe_dpi_metadata(1, matched)["scale_x"], 1.5)
        self.assertEqual(describe_dpi_metadata(3, matched)["scale_x"], 2.0)

    def test_topology_token_changes_when_primary_monitor_changes(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)
        before = topology_token(self.monitors, matched, system_metadata=self.metadata)
        changed = [dict(item) for item in self.metadata]
        changed[1]["primary"] = True
        changed[2]["primary"] = False
        changed_matched = match_monitor_metadata(self.monitors, changed)
        after = topology_token(self.monitors, changed_matched, system_metadata=changed)

        self.assertNotEqual(before, after)

    def test_topology_token_changes_when_dpi_changes(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)
        before = topology_token(self.monitors, matched, system_metadata=self.metadata)
        changed = [dict(item) for item in self.metadata]
        changed[2]["dpi_x"] = 168
        changed[2]["dpi_y"] = 168
        changed_matched = match_monitor_metadata(self.monitors, changed)
        after = topology_token(self.monitors, changed_matched, system_metadata=changed)

        self.assertNotEqual(before, after)

    def test_raw_windows_monitor_addition_changes_token_even_if_mss_cache_is_stale(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)
        before = topology_token(self.monitors, matched, system_metadata=self.metadata)
        added = [
            *self.metadata,
            {
                "left": 2560,
                "top": 0,
                "width": 1920,
                "height": 1080,
                "device": "DISPLAY4",
                "primary": False,
                "dpi_x": 96,
                "dpi_y": 96,
            },
        ]
        after = topology_token(self.monitors, matched, system_metadata=added)

        self.assertNotEqual(before, after)

    def test_same_topology_has_stable_token(self):
        matched = match_monitor_metadata(self.monitors, self.metadata)
        first = topology_token(self.monitors, matched, system_metadata=self.metadata)
        second = topology_token(self.monitors, matched, system_metadata=list(reversed(self.metadata)))

        self.assertEqual(first, second)

    def test_explicit_missing_monitor_fails_closed_in_strict_mode(self):
        with self.assertRaises(ValueError):
            select_monitor(self.monitors[:3], hint=3, strict_hint=True)

    def test_legacy_non_strict_monitor_fallback_is_preserved(self):
        selected = select_monitor(self.monitors[:3], hint=9)
        self.assertEqual(selected, self.monitors[1])


if __name__ == "__main__":
    unittest.main()
