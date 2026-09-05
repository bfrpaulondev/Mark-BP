import unittest

from core.desktop_postconditions import verify_computer_input_transition, verify_window_setting_transition


def make_state(cursor=(10, 10), foreground_hwnd=1, focus=("Edit", "field"), value=None, frame_byte=10):
    return {
        "cursor": [cursor[0], cursor[1]],
        "foreground": {"hwnd": foreground_hwnd, "exists": True},
        "target_window": {"hwnd": foreground_hwnd, "exists": True},
        "focus": {
            "control_type": focus[0],
            "automation_id": focus[1],
            "value_length": len(value) if isinstance(value, str) else None,
            "_value": value,
        },
        "frame": {"signature": str(frame_byte), "sample_length": 16, "_sample": bytes([frame_byte] * 16)},
    }


class DesktopInputPostconditionTests(unittest.TestCase):
    def test_mouse_move_requires_final_cursor_at_target(self):
        result = verify_computer_input_transition(
            "move", {"x": 300, "y": 200}, make_state(cursor=(10, 10)), make_state(cursor=(300, 200))
        )
        self.assertTrue(result.can_claim_success)

    def test_click_without_observable_effect_stays_unverified(self):
        result = verify_computer_input_transition(
            "click", {"x": 100, "y": 100}, make_state(cursor=(100, 100)), make_state(cursor=(100, 100))
        )
        self.assertFalse(result.can_claim_success)
        self.assertTrue(result.delivered)

    def test_click_with_visual_effect_is_verified(self):
        result = verify_computer_input_transition(
            "click", {"x": 100, "y": 100}, make_state(cursor=(90, 90), frame_byte=10), make_state(cursor=(100, 100), frame_byte=30)
        )
        self.assertTrue(result.can_claim_success)

    def test_scroll_requires_observable_content_change(self):
        verified = verify_computer_input_transition(
            "scroll", {"direction": "down", "amount": 3}, make_state(frame_byte=10), make_state(frame_byte=20)
        )
        unverified = verify_computer_input_transition(
            "scroll", {"direction": "down", "amount": 3}, make_state(frame_byte=10), make_state(frame_byte=10)
        )
        self.assertTrue(verified.can_claim_success)
        self.assertFalse(unverified.can_claim_success)

    def test_drag_requires_endpoint_and_observable_effect(self):
        result = verify_computer_input_transition(
            "drag", {"x1": 10, "y1": 10, "x2": 400, "y2": 250}, make_state(frame_byte=10), make_state(cursor=(400, 250), frame_byte=30)
        )
        self.assertTrue(result.can_claim_success)

    def test_typing_matches_control_value_without_exposing_value_in_evidence(self):
        typed_value = "sample-value-123"
        result = verify_computer_input_transition(
            "type", {"text": typed_value}, make_state(value=""), make_state(value=typed_value)
        )
        self.assertTrue(result.can_claim_success)
        self.assertNotIn(typed_value, repr(result.evidence))

    def test_typing_mismatch_stays_unverified(self):
        result = verify_computer_input_transition(
            "smart_type", {"text": "expected", "clear_first": True}, make_state(value="old"), make_state(value="different")
        )
        self.assertFalse(result.can_claim_success)

    def test_clear_field_requires_empty_value(self):
        result = verify_computer_input_transition("clear_field", {}, make_state(value="something"), make_state(value=""))
        self.assertTrue(result.can_claim_success)

    def test_alt_tab_requires_foreground_change(self):
        result = verify_computer_input_transition(
            "hotkey", {"keys": "alt+tab"}, make_state(foreground_hwnd=1), make_state(foreground_hwnd=2)
        )
        self.assertTrue(result.can_claim_success)

    def test_tab_press_requires_focus_change(self):
        result = verify_computer_input_transition(
            "press", {"key": "tab"}, make_state(focus=("Edit", "first")), make_state(focus=("Button", "next"))
        )
        self.assertTrue(result.can_claim_success)


class WindowSettingPostconditionTests(unittest.TestCase):
    def test_minimize_requires_iconic_target(self):
        before = {"foreground": {"hwnd": 10}, "target": {"hwnd": 10, "exists": True, "iconic": False, "zoomed": False}}
        after = {"foreground": {"hwnd": 11}, "target": {"hwnd": 10, "exists": True, "iconic": True, "zoomed": False}}
        self.assertTrue(verify_window_setting_transition("minimize", before, after).can_claim_success)

    def test_maximize_requires_zoomed_target(self):
        before = {"foreground": {"hwnd": 10}, "target": {"hwnd": 10, "exists": True, "iconic": False, "zoomed": False}}
        after = {"foreground": {"hwnd": 10}, "target": {"hwnd": 10, "exists": True, "iconic": False, "zoomed": True}}
        self.assertTrue(verify_window_setting_transition("maximize", before, after).can_claim_success)

    def test_switch_window_requires_foreground_change(self):
        before = {"foreground": {"hwnd": 10}, "target": {"hwnd": 10, "exists": True}}
        after = {"foreground": {"hwnd": 20}, "target": {"hwnd": 10, "exists": True}}
        self.assertTrue(verify_window_setting_transition("switch_window", before, after).can_claim_success)


if __name__ == "__main__":
    unittest.main()
