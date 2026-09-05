import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import doctor


class RuntimeProbeTests(unittest.TestCase):
    # -.-.-.-
    def test_probe_rejects_failed_native_import(self):
        with patch.object(doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(doctor._probe_runtime("import sounddevice"))

    # -.-.-.-
    def test_probe_bounds_time_and_discards_output(self):
        with patch.object(doctor.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 15)) as run:
            self.assertFalse(doctor._probe_runtime("import sounddevice"))
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)


class DoctorTests(unittest.TestCase):
    # -.-.-.-
    def setUp(self):
        self.probe = patch.object(doctor, "_probe_runtime", return_value=True).start()
        self.addCleanup(patch.stopall)

    # -.-.-.-
    def test_invalid_configuration_returns_report_without_secret(self):
        output = io.StringIO()
        with patch.object(doctor, "get_config", side_effect=ValueError("private-value")):
            self.assertEqual(doctor.run_doctor(output), 1)
        self.assertIn("Configuration could not be loaded", output.getvalue())
        self.assertNotIn("private-value", output.getvalue())

    # -.-.-.-
    def test_live_does_not_require_legacy_voice_extras(self):
        with patch.object(doctor, "missing_for_config", return_value=[]) as missing:
            doctor.run_doctor(io.StringIO())
        self.assertEqual(missing.call_args.args[0]["stt_engine"], "live")
        self.assertEqual(missing.call_args.args[0]["tts_engine"], "live")

    # -.-.-.-
    def test_native_failure_blocks_readiness(self):
        self.probe.return_value = False
        output = io.StringIO()
        self.assertEqual(doctor.run_doctor(output), 1)
        self.assertIn("Native audio/GUI/desktop imports failed", output.getvalue())
        self.assertIn("Default microphone and speaker failed", output.getvalue())

    # -.-.-.-
    def test_ready_environment_returns_zero(self):
        output = io.StringIO()

        with (
            patch.object(
                doctor,
                "get_config",
                return_value={"stt_engine": "whisper", "tts_engine": "edgetts", "voice_name": "Kore"},
            ),
            patch.object(doctor, "get_gemini_key", return_value="configured-key"),
            patch.object(doctor, "missing_for_config", return_value=[]),
            patch.object(doctor, "PROMPT_PATH", Path(__file__)),
            patch.object(doctor, "ANTONELLA_ENTRYPOINT", Path(__file__)),
            patch.object(doctor, "ANTONELLA_UI", Path(__file__)),
        ):
            result = doctor.run_doctor(output)

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("voice=Kore", text)
        self.assertIn("uv run python antonella.py", text)

    # -.-.-.-
    def test_missing_key_blocks_smoke_test(self):
        output = io.StringIO()

        with (
            patch.object(doctor, "get_config", return_value={}),
            patch.object(doctor, "get_gemini_key", return_value=None),
            patch.object(doctor, "missing_for_config", return_value=[]),
            patch.object(doctor, "PROMPT_PATH", Path(__file__)),
            patch.object(doctor, "ANTONELLA_ENTRYPOINT", Path(__file__)),
            patch.object(doctor, "ANTONELLA_UI", Path(__file__)),
        ):
            result = doctor.run_doctor(output)

        self.assertEqual(result, 1)
        self.assertIn("Gemini API key is missing", output.getvalue())

    # -.-.-.-
    def test_missing_dependencies_reports_explicit_locked_command(self):
        output = io.StringIO()

        with (
            patch.object(doctor, "get_config", return_value={}),
            patch.object(doctor, "get_gemini_key", return_value="configured-key"),
            patch.object(
                doctor,
                "missing_for_config",
                return_value=[("faster_whisper", "stt-whisper"), ("edge_tts", "tts-edge")],
            ),
            patch.object(doctor, "PROMPT_PATH", Path(__file__)),
            patch.object(doctor, "ANTONELLA_ENTRYPOINT", Path(__file__)),
            patch.object(doctor, "ANTONELLA_UI", Path(__file__)),
        ):
            result = doctor.run_doctor(output)

        text = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("faster_whisper, edge_tts", text)
        self.assertIn("uv sync --locked --extra stt-whisper --extra tts-edge", text)

    # -.-.-.-
    def test_direct_script_execution_bootstraps_repository_imports(self):
        root = Path(__file__).resolve().parent.parent
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "doctor.py")],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        combined = completed.stdout + completed.stderr
        self.assertNotIn("ModuleNotFoundError", combined)
        self.assertNotIn("Traceback (most recent call last)", combined)
        self.assertIn("[RESULT]", combined)
        self.assertIn(completed.returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
