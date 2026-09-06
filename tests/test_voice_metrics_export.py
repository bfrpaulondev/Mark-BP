"""Regression coverage uses runtime exports, never fabricated session files."""
import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core.voice_runtime import BargeInGate, VoiceLatency
from scripts import benchmark_voice


class VoiceMetricsExportTests(unittest.TestCase):
    def test_multiturn_export_before_reset_bounded_and_content_free(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice_metrics.json"
            latency = VoiceLatency(output_path=output, max_turns=2)
            for turn in range(3):
                latency.mark("input_transcription", turn * 10 + 1)
                latency.mark("first_response_audio", turn * 10 + 2)
                latency.complete_turn(interrupted=turn == 1)
                self.assertIsNone(latency.snapshot()["input_transcription_to_first_audio_ms"])
            document = json.loads(output.read_text())
            self.assertEqual([t["turn_id"] for t in document["turns"]], [2, 3])
            self.assertEqual(document["turns"][1]["metrics"]["input_transcription_to_first_audio_ms"], 1000)
            self.assertEqual(set(document["turns"][0]), {"turn_id", "interrupted", "metrics"})
            with patch("sys.argv", ["benchmark_voice", "--input", str(output)]), contextlib.redirect_stdout(io.StringIO()) as report:
                self.assertEqual(benchmark_voice.main(), 0)
            self.assertIn("| input_transcription_to_first_audio_ms | 1 | 1000.0 | 1000.0 |", report.getvalue())
            self.assertIn("True end-of-speech p95: NOT MEASURED", report.getvalue())
            self.assertNotIn("last_mic_frame", report.getvalue())

    def test_export_precedes_reset_and_failure_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice_metrics.json"
            latency = VoiceLatency(output_path=output)
            latency.mark("input_transcription", 1)
            latency.mark("first_response_audio", 2)
            def fail_replace(*args):
                self.assertEqual(latency.snapshot()["input_transcription_to_first_audio_ms"], 1000)
                raise OSError("disk unavailable")
            with patch("core.voice_runtime.os.replace", side_effect=fail_replace), self.assertRaises(OSError):
                latency.complete_turn()
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIsNone(latency.snapshot()["input_transcription_to_first_audio_ms"])
            latency.complete_turn()
            self.assertEqual(len(json.loads(output.read_text())["turns"]), 2)

    def test_late_mic_frames_and_transcript_updates_do_not_change_response_metric(self):
        latency = VoiceLatency()
        latency.mark("input_transcription", 1)
        latency.mark("first_response_audio", 2)
        latency.mark("input_transcription", 3)
        latency.mark("last_user_audio", 4)
        self.assertEqual(latency.snapshot()["input_transcription_to_first_audio_ms"], 1000)
        self.assertIsNone(latency.snapshot()["last_mic_frame_to_first_audio_ms"])

    def test_runtime_receive_loop_exports_at_completion(self):
        # Exercise the actual receive coroutine with dependency-free event stubs.
        import ast
        import asyncio
        from types import SimpleNamespace as NS
        module = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
        runtime = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "AntonellaRuntime")
        receive = next(n for n in runtime.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_receive_audio")
        namespace = {"asyncio": asyncio, "time": __import__("time"), "_clean_transcript": lambda text: text}
        exec(compile(ast.Module(body=[receive], type_ignores=[]), "main.py", "exec"), namespace)
        async def scenario(output):
            count = 0
            async def events():
                nonlocal count
                if count:
                    raise asyncio.CancelledError()
                count += 1
                yield NS(data=None, server_content=NS(output_transcription=None, input_transcription=NS(text="private words"), turn_complete=False), tool_call=None)
                yield NS(data=b"audio", server_content=NS(output_transcription=None, input_transcription=None, turn_complete=True), tool_call=None)
            engine = NS(session=NS(receive=events), voice_latency=VoiceLatency(output_path=output),
                        _interrupted_event=threading.Event(), _turn_done_event=threading.Event(),
                        _audio_turn=NS(current=lambda: 1), audio_in_queue=asyncio.Queue(),
                        ui=NS(write_log=lambda *args: None, set_state=lambda *args: None),
                        _session_log=[], _dashboard=None, _asst_name="Antonella",
                        _pending_vision=None, _vision_close_pending=False, _vision_active=False, _is_speaking=False)
            with self.assertRaises(asyncio.CancelledError):
                await namespace["_receive_audio"](engine)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice_metrics.json"
            asyncio.run(scenario(output))
            self.assertNotIn("private words", output.read_text())
            record = json.loads(output.read_text())["turns"][0]
            self.assertIsNotNone(record["metrics"]["input_transcription_to_first_audio_ms"])


class GateLockRegressionTests(unittest.TestCase):
    def test_parallel_feeds_are_serialized_exactly(self):
        gate = BargeInGate(enabled=True, threshold=100, frames_above=2, cooldown_seconds=0)
        barrier = threading.Barrier(8)
        fires = []
        def feed():
            barrier.wait(timeout=5)
            fires.extend(gate.feed(200, 10) for _ in range(100))
        threads = [threading.Thread(target=feed) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sum(fires), 400)
        # Prove feed acquires the very lock guarding its transition.
        entered = threading.Event()
        finished = threading.Event()
        class ObservedLock:
            def __enter__(self):
                entered.set()
                underlying.acquire()
            def __exit__(self, *args): underlying.release()
        underlying = threading.Lock()
        gate._lock = ObservedLock()
        underlying.acquire()
        thread = threading.Thread(target=lambda: (gate.feed(200, 11), finished.set()))
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertFalse(finished.is_set())
        finally:
            underlying.release()
            thread.join(timeout=5)
        self.assertTrue(finished.is_set())
