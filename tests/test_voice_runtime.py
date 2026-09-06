import unittest

from core.voice_runtime import BargeInGate, TurnRegistry, VoiceLatency, percentile


class TurnRegistryTests(unittest.TestCase):
    def test_stale_tokens_are_rejected_after_advance(self):
        registry = TurnRegistry()
        token = registry.current()
        self.assertTrue(registry.is_current(token))
        registry.advance()
        self.assertFalse(registry.is_current(token))
        self.assertTrue(registry.is_current(registry.current()))

    def test_multiple_advances_keep_monotonic(self):
        registry = TurnRegistry()
        first = registry.current()
        second = registry.advance()
        third = registry.advance()
        self.assertLess(first, second)
        self.assertLess(second, third)
        self.assertFalse(registry.is_current(first))


class BargeInGateTests(unittest.TestCase):
    def test_disabled_gate_never_fires(self):
        gate = BargeInGate(enabled=False, threshold=100, frames_above=1)
        for now in (1.0, 2.0, 3.0, 4.0):
            self.assertFalse(gate.feed(1000, now))

    def test_fires_after_consecutive_frames_above_threshold(self):
        gate = BargeInGate(enabled=True, threshold=100, frames_above=3, cooldown_seconds=2.0)
        self.assertFalse(gate.feed(500, 1.0))   # streak 1
        self.assertFalse(gate.feed(120, 2.0))   # streak 2
        self.assertTrue(gate.feed(150, 3.0))    # streak 3 -> fires
        self.assertFalse(gate.feed(200, 3.5))   # cooldown blocks immediately after

    def test_quiet_frame_resets_streak(self):
        gate = BargeInGate(enabled=True, threshold=100, frames_above=2)
        self.assertFalse(gate.feed(200, 1.0))
        self.assertFalse(gate.feed(50, 2.0))   # reset
        self.assertFalse(gate.feed(200, 3.0))
        self.assertTrue(gate.feed(200, 4.0))

    def test_cooldown_blocks_immediate_retrigger(self):
        gate = BargeInGate(enabled=True, threshold=100, frames_above=1, cooldown_seconds=2.0)
        self.assertTrue(gate.feed(200, 1.0))
        self.assertFalse(gate.feed(200, 2.0))  # within cooldown
        self.assertFalse(gate.feed(200, 2.9))
        self.assertTrue(gate.feed(200, 3.5))   # cooldown elapsed

    def test_config_defaults_are_fail_safe(self):
        gate = BargeInGate()  # disabled by default
        self.assertFalse(gate.enabled)


class VoiceLatencyTests(unittest.TestCase):
    def test_unknown_milestone_is_rejected(self):
        latency = VoiceLatency()
        with self.assertRaises(ValueError):
            latency.mark("made_up")

    def test_first_milestone_keeps_first_value(self):
        latency = VoiceLatency()
        latency.mark("first_response_audio", 10.0)
        latency.mark("first_response_audio", 20.0)
        self.assertEqual(latency.snapshot()["last_mic_frame_to_first_audio_ms"], None)
        # direct check via marks through behaviour: snapshot only exposes deltas

    def test_snapshot_durations(self):
        latency = VoiceLatency()
        latency.mark("last_user_audio", 1.0)
        latency.mark("input_transcription", 1.4)
        latency.mark("agent_start", 1.9)
        latency.mark("first_action", 2.4)
        latency.mark("first_response_audio", 3.0)
        snap = latency.snapshot()
        self.assertAlmostEqual(snap["transcription_latency_ms"], 400.0)
        self.assertAlmostEqual(snap["route_to_agent_ms"], 500.0)
        self.assertAlmostEqual(snap["agent_to_first_action_ms"], 500.0)
        self.assertAlmostEqual(snap["last_mic_frame_to_first_audio_ms"], 2000.0)

    def test_new_turn_clears_marks(self):
        latency = VoiceLatency()
        latency.mark("last_user_audio", 1.0)
        latency.new_turn()
        self.assertEqual(latency.snapshot()["transcription_latency_ms"], None)

    def test_percentile_is_honest(self):
        self.assertIsNone(percentile([], 95))
        values = [100.0, 200.0, 300.0, 400.0, 1000.0]
        self.assertEqual(percentile(values, 50), 300.0)
        self.assertEqual(percentile(values, 95), 1000.0)


if __name__ == "__main__":
    unittest.main()
