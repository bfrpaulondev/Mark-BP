from __future__ import annotations

import unittest

from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.computer_use.recovery import (
    RecoveryPolicy,
    RecoveryState,
    action_uses_planned_coordinates,
    frame_is_superseded,
    target_scope_is_valid,
)


def _frame(sequence: int, *, scope: str = "monitor") -> FrameSnapshot:
    return FrameSnapshot(
        sequence=sequence,
        timestamp=1.0,
        left=0,
        top=0,
        monitor_width=1920,
        monitor_height=1080,
        image_width=1280,
        image_height=720,
        monitor_index=1,
        change_score=0.1,
        jpeg_bytes=b"x",
        capture_scope=scope,
        topology_token="topology-1",
    )


class ComputerUseRecoveryTests(unittest.TestCase):
    def test_policy_is_bounded_by_step_budget(self) -> None:
        self.assertEqual(4, RecoveryPolicy.for_step_budget(1).max_recoveries)
        self.assertEqual(10, RecoveryPolicy.for_step_budget(100).max_recoveries)

    def test_settle_timeout_grows_but_stays_bounded(self) -> None:
        policy = RecoveryPolicy()
        action = ComputerAction(action="click")
        first = policy.settle_timeout(action, 0)
        later = policy.settle_timeout(action, 20)
        self.assertGreater(later, first)
        self.assertLessEqual(later, policy.max_settle_timeout)

    def test_only_scroll_is_automatically_retry_safe(self) -> None:
        state = RecoveryState()
        policy = RecoveryPolicy(max_safe_action_retries=1)
        scroll = ComputerAction(action="scroll")
        click = ComputerAction(action="click")
        typed = ComputerAction(action="type", text="example")

        self.assertTrue(state.can_retry_action(scroll, policy))
        self.assertFalse(state.can_retry_action(click, policy))
        self.assertFalse(state.can_retry_action(typed, policy))
        state.note_action_retry(scroll)
        self.assertFalse(state.can_retry_action(scroll, policy))
        self.assertEqual(1, state.safe_action_retries)

    def test_visual_change_resets_no_change_and_retry_budget(self) -> None:
        state = RecoveryState()
        policy = RecoveryPolicy(max_safe_action_retries=1)
        scroll = ComputerAction(action="scroll")
        state.note_visual_change(False)
        state.note_action_retry(scroll)
        self.assertEqual(1, state.no_change_streak)
        self.assertFalse(state.can_retry_action(scroll, policy))

        state.note_visual_change(True)
        self.assertEqual(0, state.no_change_streak)
        self.assertTrue(state.can_retry_action(scroll, policy))

    def test_recovery_limit_is_fail_closed(self) -> None:
        policy = RecoveryPolicy(max_recoveries=2)
        state = RecoveryState()
        self.assertTrue(state.can_recover(policy))
        state.note_recovery("first")
        self.assertTrue(state.can_recover(policy))
        state.note_recovery("second")
        self.assertFalse(state.can_recover(policy))

    def test_recovery_snapshot_contains_only_operational_metadata(self) -> None:
        state = RecoveryState()
        state.note_recovery("stale frame", kind="stale")
        state.note_recovery("target scope unavailable", kind="reacquire")
        snapshot = state.snapshot()
        self.assertEqual(2, snapshot["recoveries"])
        self.assertEqual(1, snapshot["stale_replans"])
        self.assertEqual(1, snapshot["target_reacquisitions"])
        self.assertNotIn("objective", snapshot)
        self.assertNotIn("text", snapshot)

    def test_newer_emitted_frame_invalidates_plan(self) -> None:
        planned = _frame(5)
        self.assertFalse(frame_is_superseded(planned, _frame(5)))
        self.assertFalse(frame_is_superseded(planned, _frame(4)))
        self.assertTrue(frame_is_superseded(planned, _frame(6)))

    def test_target_window_requires_window_capture_scope(self) -> None:
        self.assertTrue(target_scope_is_valid(_frame(1), ""))
        self.assertFalse(target_scope_is_valid(_frame(1, scope="monitor"), "Editor"))
        self.assertTrue(target_scope_is_valid(_frame(1, scope="window"), "Editor"))

    def test_coordinate_actions_are_explicit(self) -> None:
        for action_name in ("click", "double_click", "right_click", "move"):
            self.assertTrue(action_uses_planned_coordinates(ComputerAction(action=action_name)))
        for action_name in ("scroll", "type", "hotkey", "press", "wait"):
            self.assertFalse(action_uses_planned_coordinates(ComputerAction(action=action_name)))


if __name__ == "__main__":
    unittest.main()
