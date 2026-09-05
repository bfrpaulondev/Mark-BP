import unittest

from actions.real_browser_control import _select_tab, _select_window, _url_matches


class RealBrowserWindowSelectionTests(unittest.TestCase):
    def setUp(self):
        self.windows = [
            {"hwnd": 10, "browser": "chrome", "title": "GitHub - Google Chrome", "area": 1000},
            {"hwnd": 20, "browser": "chrome", "title": "Docs - Google Chrome", "area": 900},
            {"hwnd": 30, "browser": "edge", "title": "Dashboard - Microsoft Edge", "area": 800},
        ]

    def test_explicit_window_index_selects_real_window(self):
        selected, reason = _select_window(self.windows, "chrome", "2", foreground_hwnd=0)
        self.assertEqual(selected["hwnd"], 20)
        self.assertEqual(reason, "index")

    def test_window_title_fragment_selects_unique_window(self):
        selected, reason = _select_window(self.windows, "chrome", "github", foreground_hwnd=0)
        self.assertEqual(selected["hwnd"], 10)
        self.assertEqual(reason, "title")

    def test_foreground_window_is_preferred_when_browser_matches(self):
        selected, reason = _select_window(self.windows, "chrome", None, foreground_hwnd=20)
        self.assertEqual(selected["hwnd"], 20)
        self.assertEqual(reason, "foreground")

    def test_multiple_matching_windows_fail_closed_instead_of_guessing(self):
        selected, reason = _select_window(self.windows, "chrome", None, foreground_hwnd=0)
        self.assertIsNone(selected)
        self.assertIn("Multiple browser windows", reason)

    def test_multiple_browser_apps_fail_closed_without_browser_selector(self):
        selected, reason = _select_window(self.windows, "", None, foreground_hwnd=0)
        self.assertIsNone(selected)
        self.assertIn("Multiple browser applications", reason)


class RealBrowserTabSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tabs = [
            {"index": 1, "name": "Inbox", "selected": False},
            {"index": 2, "name": "GitHub · Mark-BP", "selected": True},
            {"index": 12, "name": "FastAPI Documentation", "selected": False},
        ]

    def test_tab_index_is_not_limited_to_nine_when_uia_exposes_tabs(self):
        selected, reason = _select_tab(self.tabs, "12")
        self.assertEqual(selected["name"], "FastAPI Documentation")
        self.assertEqual(reason, "index")

    def test_tab_title_fragment_selects_unique_tab(self):
        selected, reason = _select_tab(self.tabs, "mark-bp")
        self.assertEqual(selected["index"], 2)
        self.assertEqual(reason, "title")

    def test_ambiguous_tab_title_fails_closed(self):
        tabs = self.tabs + [{"index": 13, "name": "GitHub · Issues", "selected": False}]
        selected, reason = _select_tab(tabs, "github")
        self.assertIsNone(selected)
        self.assertIn("More than one", reason)

    def test_url_fragment_matching_is_case_insensitive(self):
        self.assertTrue(_url_matches("https://github.com/bfrpaulondev/Mark-BP", "GITHUB.COM/bfrpaulondev"))
        self.assertFalse(_url_matches("https://example.com", "github.com"))


if __name__ == "__main__":
    unittest.main()
