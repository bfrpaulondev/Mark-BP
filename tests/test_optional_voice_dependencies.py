import asyncio
import builtins
import importlib
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _fail_import(module_name: str, message: str | None = None):
    real_import = builtins.__import__

    def import_with_failure(name, globals=None, locals=None, fromlist=(), level=0):
        if name == module_name:
            raise ModuleNotFoundError(
                message or f"No module named '{module_name}'",
                name=module_name,
            )
        return real_import(name, globals, locals, fromlist, level)

    return patch("builtins.__import__", side_effect=import_with_failure)


class OptionalVoiceDependenciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_numpy = sys.modules.get("numpy")
        cls._original_sounddevice = sys.modules.get("sounddevice")
        fake_numpy = types.ModuleType("numpy")
        fake_numpy.ndarray = type("ndarray", (), {})
        fake_sounddevice = types.ModuleType("sounddevice")
        fake_sounddevice.play = lambda *_args, **_kwargs: None
        fake_sounddevice.wait = lambda: None
        fake_sounddevice.stop = lambda: None
        sys.modules["numpy"] = fake_numpy
        sys.modules["sounddevice"] = fake_sounddevice
        sys.modules.pop("core.stt", None)
        sys.modules.pop("core.tts", None)
        cls.stt = importlib.import_module("core.stt")
        cls.tts = importlib.import_module("core.tts")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("core.stt", None)
        sys.modules.pop("core.tts", None)
        if cls._original_numpy is None:
            sys.modules.pop("numpy", None)
        else:
            sys.modules["numpy"] = cls._original_numpy
        if cls._original_sounddevice is None:
            sys.modules.pop("sounddevice", None)
        else:
            sys.modules["sounddevice"] = cls._original_sounddevice

    def test_voice_extras_are_declared(self):
        import tomllib

        project_root = Path(__file__).resolve().parents[1]
        manifest = tomllib.loads(
            (project_root / "pyproject.toml").read_text(encoding="utf-8")
        )

        self.assertEqual(
            set(manifest["project"]["optional-dependencies"]),
            {
                "stt-whisper",
                "stt-vosk",
                "tts-edge",
                "tts-elevenlabs",
                "tts-kokoro",
            },
        )

    def test_whisper_missing_dependency_has_actionable_error(self):
        with _fail_import("faster_whisper"):
            with self.assertRaisesRegex(
                RuntimeError,
                r"uv sync --locked --extra stt-whisper",
            ):
                self.stt.WhisperSTT()

    def test_vosk_missing_dependency_has_actionable_error(self):
        with _fail_import("vosk"):
            with self.assertRaisesRegex(
                RuntimeError,
                r"uv sync --locked --extra stt-vosk",
            ):
                self.stt.VoskSTT()

    def test_edge_tts_missing_dependency_has_actionable_error(self):
        with _fail_import("edge_tts"):
            with self.assertRaisesRegex(
                RuntimeError,
                r"uv sync --locked --extra tts-edge",
            ):
                asyncio.run(self.tts.EdgeTTSEngine()._synth("hello"))

    def test_miniaudio_missing_dependency_has_actionable_error(self):
        with _fail_import("miniaudio"):
            with self.assertRaisesRegex(
                RuntimeError,
                r"uv sync --locked --extra tts-edge",
            ):
                self.tts._play_audio_bytes(b"")

    def test_kokoro_compatibility_error_never_installs_packages(self):
        with _fail_import("kokoro", "cannot import name 'AutoModel'"):
            with patch.object(subprocess, "run") as run:
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"uv sync --locked --extra tts-kokoro",
                ):
                    self.tts._import_kokoro_pipeline()

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
