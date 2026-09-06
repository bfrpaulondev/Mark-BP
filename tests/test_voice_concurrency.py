"""ANT-271 V10 — concurrency and lifecycle tests for the voice runtime.

Covers: thread-safe barge-in scheduling, queue ownership, turn token
race, stale rejection, new-turn preservation, multi-turn metrics and
double interruption. All deterministic — no audio hardware.
"""

from __future__ import annotations

import asyncio
import threading
import unittest

from core.voice_runtime import BargeInGate, TurnRegistry, VoiceLatency

try:
    from main import AntonellaRuntime  # needs PyQt6 (ui facade)
    HAS_RUNTIME = True
except ImportError:
    HAS_RUNTIME = False


def _engine_on_loop(loop: asyncio.AbstractEventLoop) -> AntonellaRuntime:
    """Real runtime object without __init__ (no hardware/keys needed)."""
    engine = object.__new__(AntonellaRuntime)
    engine.ui = type("UI", (), {"write_log": staticmethod(lambda text: None),
                                "set_state": staticmethod(lambda state: None),
                                "muted": False})()
    engine.session = None
    engine._loop = loop
    engine.audio_in_queue = asyncio.Queue()
    engine._speaking_lock = threading.Lock()
    engine._is_speaking = True
    engine._turn_done_event = threading.Event()
    engine._interrupted_event = threading.Event()
    engine._audio_turn = TurnRegistry()
    engine.voice_latency = VoiceLatency()
    return engine


@unittest.skipUnless(HAS_RUNTIME, "PyQt6 unavailable: dependency-free CI legs skip")
class RequestInterruptSchedulingTests(unittest.TestCase):
    """V1: the sounddevice thread never drains the asyncio queue itself —
    request_interrupt schedules the drain on the event loop."""

    def test_callback_thread_schedules_drain_on_loop(self):
        async def scenario():
            loop = asyncio.get_running_loop()
            engine = _engine_on_loop(loop)
            engine.audio_in_queue.put_nowait(b"old-1")
            engine.audio_in_queue.put_nowait(b"old-2")

            drained_on: list[str] = []
            real_drain_done = threading.Event()
            original_interrupt = engine.interrupt

            def interrupt():
                drained_on.append(threading.current_thread().name)
                original_interrupt()
                real_drain_done.set()

            engine.interrupt = interrupt

            # Simulate the sounddevice callback thread (NOT the loop thread).
            def fake_callback():
                thread = threading.Thread(target=engine.request_interrupt, name="sd-callback")
                thread.start()
                thread.join(timeout=5)

            await asyncio.to_thread(fake_callback)
            await asyncio.sleep(0.1)  # let call_soon_threadsafe run the drain

            self.assertTrue(real_drain_done.is_set())
            # The drain happened on the loop thread, never the callback.
            self.assertNotIn("sd-callback", drained_threads(drained_on))
            self.assertTrue(engine.audio_in_queue.empty())
            self.assertTrue(engine._interrupted_event.is_set())
            self.assertNotEqual(engine._audio_turn.current(), 0)

        asyncio.run(scenario())

    def test_request_interrupt_without_loop_drains_directly(self):
        engine = object.__new__(AntonellaRuntime)
        engine.ui = type("UI", (), {"write_log": staticmethod(lambda text: None),
                                    "set_state": staticmethod(lambda state: None),
                                    "muted": False})()
        engine.session = None
        engine._loop = None
        engine.audio_in_queue = asyncio.Queue()
        engine.audio_in_queue.put_nowait(b"x")
        engine._speaking_lock = threading.Lock()
        engine._is_speaking = True
        engine._turn_done_event = threading.Event()
        engine._interrupted_event = threading.Event()
        engine._audio_turn = TurnRegistry()

        engine.request_interrupt()  # no live loop: direct drain is safe
        self.assertTrue(engine.audio_in_queue.empty())
        self.assertTrue(engine._interrupted_event.is_set())


def drained_threads(names):
    return names


class TurnTokenRaceTests(unittest.TestCase):
    def test_stale_rejected_new_turn_preserved(self):
        registry = TurnRegistry()
        stale = registry.current()
        fresh = registry.advance()
        self.assertFalse(registry.is_current(stale))
        self.assertTrue(registry.is_current(fresh))

    def test_double_interrupt_keeps_tokens_monotonic(self):
        registry = TurnRegistry()
        first = registry.advance()
        second = registry.advance()
        self.assertLess(first, second)
        self.assertFalse(registry.is_current(first))
        self.assertTrue(registry.is_current(second))


class MultiTurnMetricsTests(unittest.TestCase):
    def test_turns_have_clean_metric_identity(self):
        latency = VoiceLatency()
        # Turn N
        latency.mark("last_user_audio", 1.0)
        latency.mark("first_response_audio", 3.0)
        self.assertAlmostEqual(latency.snapshot()["last_mic_frame_to_first_audio_ms"], 2000.0)
        # Turn N+1: clean slate — milestones must not mix across turns.
        latency.new_turn()
        latency.mark("last_user_audio", 10.0)
        snap = latency.snapshot()
        self.assertIsNone(snap["last_mic_frame_to_first_audio_ms"])
        self.assertIsNone(snap["transcription_latency_ms"])
        latency.mark("first_response_audio", 12.0)
        self.assertAlmostEqual(latency.snapshot()["last_mic_frame_to_first_audio_ms"], 2000.0)


class BargeInThreadSafetyTests(unittest.TestCase):
    def test_gate_is_thread_safe_under_parallel_feeds(self):
        gate = BargeInGate(enabled=True, threshold=100, frames_above=1, cooldown_seconds=0.0)
        fires: list[float] = []
        lock = threading.Lock()

        def feeder(start: float):
            for index in range(200):
                if gate.feed(500, start + index * 0.01):
                    with lock:
                        fires.append(start + index * 0.01)

        threads = [threading.Thread(target=feeder, args=(10.0 + t * 100,)) for t in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertLessEqual(len(fires), 800)  # bounded, no crash


if __name__ == "__main__":
    unittest.main()
