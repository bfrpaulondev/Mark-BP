import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import doctor


class DoctorTests(unittest.TestCase):
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
