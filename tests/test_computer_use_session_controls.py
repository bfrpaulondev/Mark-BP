from __future__ import annotations

import unittest

from core.computer_use.contracts import FrameSnapshot, SessionState
from core.computer_use.recovery import RecoveryPolicy, RecoveryState
from core.computer_use.session import RealtimeComputerUseSession


class _AliveThread:
    def is_alive(self) -> bool:
        return True


class _CaptureSequence:
    def __init__(self, frames: list[FrameSnapshot]):
        self._frames = list(frames)
        self._index = 0

    def latest(self, timeout: float = 0.0) -> FrameSnapshot:
        frame = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        return frame


def _frame(sequence: int, scope: str) -> FrameSnapshot:
    return FrameSnapshot(
        sequence=sequence,
        timestamp=1.0,
        left=0,
        top=0,
        monitor_width=1280,
        monitor_height=720,
        image_width=1280,
        image_height=720,
        monitor_index=1,
        change_score=0.2,
        jpeg_bytes=b"x",
        capture_scope=scope,
        topology_token="topology-1",
    )


class ComputerUseSessionControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = RealtimeComputerUseSession()
        self.session._thread = _AliveThread()  # type: ignore[assignment]
        self.session._state = SessionState(state="observing")

    def test_pause_and_resume_are_idempotent(self) -> None:
        paused = self.session.pause()
        self.assertTrue(paused["ok"])
        self.assertTrue(paused["status"]["paused"])
        self.assertEqual("paused", paused["status"]["state"])

        paused_again = self.session.pause()
        self.assertTrue(paused_again["ok"])
        self.assertTrue(paused_again["status"]["paused"])

        resumed = self.session.resume()
        self.assertTrue(resumed["ok"])
        self.assertFalse(resumed["status"]["paused"])
        self.assertEqual("observing", resumed["status"]["state"])

        resumed_again = self.session.resume()
        self.assertTrue(resumed_again["ok"])
        self.assertFalse(resumed_again["status"]["paused"])

    def test_resume_restores_waiting_approval_state(self) -> None:
        self.session._state.awaiting_approval = True
        self.session.pause()
        resumed = self.session.resume()
        self.assertEqual("awaiting_approval", resumed["status"]["state"])
        self.assertTrue(resumed["status"]["awaiting_approval"])

    def test_approval_while_paused_does_not_resume_execution(self) -> None:
        self.session._state.awaiting_approval = True
        self.session.pause()
        approved = self.session.approve_once()
        self.assertTrue(approved["ok"])
        self.assertTrue(approved["status"]["paused"])
        self.assertEqual("paused", approved["status"]["state"])
        self.assertFalse(approved["status"]["awaiting_approval"])

    def test_stop_releases_pause_wait(self) -> None:
        self.session.pause()
        stopped = self.session.stop()
        self.assertTrue(stopped["ok"])
        self.assertFalse(stopped["status"]["paused"])
        self.assertEqual("stopping", stopped["status"]["state"])
        self.assertTrue(self.session._resume_event.is_set())

    def test_pause_without_active_thread_fails_closed(self) -> None:
        inactive = RealtimeComputerUseSession()
        result = inactive.pause()
        self.assertFalse(result["ok"])
        self.assertIn("No active", result["error"])

    def test_target_reacquisition_waits_for_window_scope(self) -> None:
        self.session._state.target_window = "Editor"
        self.session._focus_target_window = lambda: "Focus requested"  # type: ignore[method-assign]
        capture = _CaptureSequence(
            [_frame(1, "monitor"), _frame(2, "monitor"), _frame(3, "window")]
        )
        recovery = RecoveryState()
        policy = RecoveryPolicy(reacquire_timeout=1.0)

        result = self.session._recover_target_window(
            capture,
            recovery,
            policy,
            reason="target scope lost",
        )

        self.assertIsNotNone(result)
        self.assertEqual("window", result.capture_scope)
        self.assertEqual(1, recovery.target_reacquisitions)
        self.assertTrue(self.session.status()["target_locked"])

    def test_target_reacquisition_stops_when_focus_fails(self) -> None:
        self.session._state.target_window = "Editor"
        self.session._focus_target_window = lambda: "focus_window failed: missing"  # type: ignore[method-assign]
        recovery = RecoveryState()
        policy = RecoveryPolicy(reacquire_timeout=1.0)

        result = self.session._recover_target_window(
            _CaptureSequence([_frame(1, "monitor")]),
            recovery,
            policy,
            reason="target scope lost",
        )

        self.assertIsNone(result)
        self.assertEqual(1, recovery.target_reacquisitions)
        self.assertFalse(self.session.status()["target_locked"])


if __name__ == "__main__":
    unittest.main()
