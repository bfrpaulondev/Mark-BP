import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import doctor


class DoctorTests(unittest.TestCase):
    # -.-.-.-
    def test_ready_environment_returns_zero(self):
        output = io.StringIO()

        with (
            patch.object(doctor, "get_config", return_value={"stt_engine": "whisper", "tts_engine": "edgetts"}),
            patch.object(doctor, "get_gemini_key", return_value="configured-key"),
            patch.object(doctor, "missing_for_config", return_value=[]),
            patch.object(doctor, "PROMPT_PATH", Path(__file__)),
        ):
            result = doctor.run_doctor(output)

        self.assertEqual(result, 0)
        self.assertIn("Antonella is ready for a local smoke test", output.getvalue())

    # -.-.-.-
    def test_missing_key_blocks_smoke_test(self):
        output = io.StringIO()

        with (
            patch.object(doctor, "get_config", return_value={}),
            patch.object(doctor, "get_gemini_key", return_value=None),
            patch.object(doctor, "missing_for_config", return_value=[]),
            patch.object(doctor, "PROMPT_PATH", Path(__file__)),
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
        ):
            result = doctor.run_doctor(output)

        text = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("faster_whisper, edge_tts", text)
        self.assertIn("uv sync --locked --extra stt-whisper --extra tts-edge", text)


if __name__ == "__main__":
    unittest.main()
