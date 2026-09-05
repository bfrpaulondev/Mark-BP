from __future__ import annotations

import unittest

from core.computer_use.contracts import SessionState
from core.computer_use.session import RealtimeComputerUseSession


class _AliveThread:
    def is_alive(self) -> bool:
        return True


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


if __name__ == "__main__":
    unittest.main()
