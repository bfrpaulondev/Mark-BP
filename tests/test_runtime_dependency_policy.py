import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import dev_agent
from core import installer


class RuntimeDependencyPolicyTests(unittest.TestCase):
    # -.-.-.-
    def test_installer_reports_missing_dependencies_without_installing(self):
        logs: list[str] = []

        with patch.object(installer, "_available", return_value=False), patch.object(
            installer.platform, "system", return_value="Linux"
        ):
            installer.install_for_config(
                {"stt_engine": "vosk", "tts_engine": "edgetts"},
                logs.append,
            )

        output = "\n".join(logs)
        self.assertIn("Runtime installation is disabled", output)
        self.assertIn("uv sync --locked", output)
        self.assertIn("--extra stt-vosk", output)
        self.assertIn("--extra tts-edge", output)

    # -.-.-.-
    def test_dev_agent_declares_dependencies_without_running_pip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with patch.object(dev_agent.subprocess, "run") as subprocess_run:
                result = dev_agent._install_dependencies(
                    ["requests>=2.0", "pydantic==2.12.5"],
                    project_dir,
                )

            subprocess_run.assert_not_called()
            self.assertEqual(
                (project_dir / "requirements.txt").read_text(encoding="utf-8"),
                "requests>=2.0\npydantic==2.12.5\n",
            )
            self.assertIn("Install explicitly", result)

    # -.-.-.-
    def test_dependency_errors_stop_with_explicit_install_instruction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "requirements.txt").write_text(
                "requests\n",
                encoding="utf-8",
            )

            message = dev_agent._dependency_error_message(
                project_dir,
                "ModuleNotFoundError: No module named 'requests'",
            )

        self.assertIn("Runtime dependency installation is disabled", message)
        self.assertIn("pip install -r requirements.txt", message)
        self.assertIn("requests", message)


if __name__ == "__main__":
    unittest.main()
