import json
import unittest
from unittest.mock import patch

from actions.real_browser_cdp import (
    _endpoint,
    _is_chromium_probe,
    _probe,
    _safe_connect_kwargs,
    _select_record,
    _validate_port,
    real_browser_cdp,
)
from plugins import verified_desktop_control as plugin


class RealBrowserCdpSafetyTests(unittest.TestCase):
    def test_endpoint_is_always_loopback_and_port_is_explicit(self):
        self.assertEqual(_endpoint(9222), "http://127.0.0.1:9222")
        self.assertEqual(_validate_port(None), 9222)
        self.assertEqual(_validate_port("9333"), 9333)
        with self.assertRaises(ValueError):
            _validate_port(80)
        with self.assertRaises(ValueError):
            _validate_port(70000)

    def test_probe_redacts_websocket_and_user_agent_metadata(self):
        payload = {
            "Browser": "Chrome/147.0",
            "Protocol-Version": "1.3",
            "User-Agent": "secret-ish-agent",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/private-id",
        }
        with patch("actions.real_browser_cdp._http_json", return_value=payload):
            result = _probe(9222)

        self.assertEqual(result["browser"], "Chrome/147.0")
        self.assertEqual(result["protocol_version"], "1.3")
        self.assertTrue(result["chromium"])
        self.assertNotIn("webSocketDebuggerUrl", result)
        self.assertNotIn("User-Agent", result)

    def test_only_chromium_family_probe_is_accepted(self):
        self.assertTrue(_is_chromium_probe({"Browser": "Chrome/147.0"}))
        self.assertTrue(_is_chromium_probe({"Browser": "Chromium/147.0"}))
        self.assertTrue(_is_chromium_probe({"Browser": "Edg/147.0"}))
        self.assertFalse(_is_chromium_probe({"Browser": "Firefox/150.0"}))

    def test_safe_attach_requires_no_defaults_capability(self):
        async def modern(endpoint_url, *, timeout=30000, is_local=False, no_defaults=False):
            return None

        async def old(endpoint_url, *, timeout=30000):
            return None

        modern_kwargs = _safe_connect_kwargs(modern)
        self.assertEqual(
            modern_kwargs,
            {"timeout": 3000, "no_defaults": True, "is_local": True},
        )
        self.assertIsNone(_safe_connect_kwargs(old))

    def test_firefox_is_rejected_before_any_endpoint_probe(self):
        with patch("actions.real_browser_cdp._probe") as probe:
            payload = json.loads(
                real_browser_cdp(
                    {"action": "browser_cdp_status", "browser": "firefox", "cdp_port": 9222}
                )
            )

        self.assertFalse(payload["verified"])
        self.assertIn("Chromium", payload["error"])
        probe.assert_not_called()

    def test_status_checks_only_the_requested_port(self):
        with patch(
            "actions.real_browser_cdp._probe",
            return_value={"browser": "Chrome/147", "protocol_version": "1.3", "chromium": True},
        ) as probe:
            payload = json.loads(
                real_browser_cdp({"action": "browser_cdp_status", "cdp_port": 9444})
            )

        self.assertTrue(payload["verified"])
        self.assertEqual(payload["evidence"]["endpoint"], "127.0.0.1:9444")
        probe.assert_called_once_with(9444)


class RealBrowserCdpSelectionTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"index": 1, "title": "Docs", "url": "https://example.test/docs"},
            {"index": 2, "title": "Dashboard", "url": "https://app.test/home"},
            {"index": 3, "title": "Settings", "url": "https://app.test/settings"},
        ]

    def test_tab_can_be_selected_by_index_title_or_url(self):
        self.assertEqual(_select_record(self.records, tab="2"), (2, None))
        self.assertEqual(_select_record(self.records, tab="Settings"), (3, None))
        self.assertEqual(_select_record(self.records, url="/docs"), (1, None))

    def test_ambiguous_title_fails_closed(self):
        records = [
            {"index": 1, "title": "Project Docs", "url": "https://a.test"},
            {"index": 2, "title": "API Docs", "url": "https://b.test"},
        ]
        index, error = _select_record(records, tab="Docs")
        self.assertIsNone(index)
        self.assertIn("Multiple", error)


class RealBrowserCdpPluginTests(unittest.TestCase):
    def test_plugin_exposes_cdp_actions_without_host_or_endpoint_parameters(self):
        properties = plugin.PLUGIN["parameters"]["properties"]
        action_description = properties["action"]["description"]
        self.assertIn("browser_cdp_status", action_description)
        self.assertIn("browser_cdp_list_tabs", action_description)
        self.assertIn("browser_cdp_switch_tab", action_description)
        self.assertIn("cdp_port", properties)
        self.assertNotIn("host", properties)
        self.assertNotIn("endpoint", properties)

    def test_cdp_actions_route_to_safe_cdp_controller(self):
        with patch.object(plugin, "real_browser_cdp", return_value='{"verified":true}') as cdp:
            with patch.object(plugin, "real_browser_control") as real_browser:
                with patch.object(plugin, "verified_desktop_control") as mouse:
                    result = plugin.run({"action": "browser_cdp_status", "cdp_port": 9222})

        self.assertEqual(result, '{"verified":true}')
        cdp.assert_called_once()
        real_browser.assert_not_called()
        mouse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
