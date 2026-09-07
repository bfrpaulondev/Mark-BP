"""Startup binding regression (ANT-275 physical round 2).

The physical Windows round found `AntonellaRuntime.__init__` calling
`get_config()` while main.py imported only `get_gemini_key` — a
NameError that compileall and import-only CI could not catch because it
fires at CONSTRUCTION time, not at import time.

This module constructs the real runtime offscreen, executing the full
`__init__` binding path, and asserts the barge-in gate arrives from the
typed settings with the desktop default ENABLED. Requires PyQt6: runs
in the ui-widget CI job, skipped on dependency-free legs.

Hygiene: heavy third-party modules main.py imports at module level
(sounddevice, google.genai) that the test environment may lack are
shimmed in sys.modules ONLY while main is first imported, then removed
— otherwise doctor's importlib.util.find_spec() breaks on stub modules
(__spec__ is None).
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HEAVY_IMPORTS = ("sounddevice", "google", "google.genai", "google.genai.types")

_HAS_QT = importlib.util.find_spec("PyQt6") is not None
_MISSING = object()


class _ImportOnlyProviderType:
    """Annotation stand-in; provider code must never run on this shim."""

    # -.-.-.-
    def __init__(self, *args, **kwargs):
        raise AssertionError("The startup import shim cannot execute provider code")


# -.-.-.-
def _restore_sys_modules(saved: dict[str, object]) -> None:
    for name, module in reversed(list(saved.items())):
        if module is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


# -.-.-.-
def _import_runtime():
    saved: dict[str, object] = {}
    try:
        # Existing entries, including None import blockers, are never replaced.
        # A missing transitive dependency is an import failure, not a shim target.
        for name in HEAVY_IMPORTS:
            if name in sys.modules:
                continue
            try:
                importlib.import_module(name)
            except ModuleNotFoundError as exc:
                if exc.name != name:
                    raise
                stub = types.ModuleType(name)
                stub.__path__ = []
                stub.__spec__ = importlib.machinery.ModuleSpec(name, None)
                if name == "google.genai.types":
                    # main evaluates these annotations while defining the class.
                    stub.LiveConnectConfig = _ImportOnlyProviderType
                    stub.FunctionResponse = _ImportOnlyProviderType
                saved[name] = _MISSING
                sys.modules[name] = stub
        return importlib.import_module("main")
    finally:
        _restore_sys_modules(saved)


# Import once during discovery so the existing concurrency tests can use the
# real runtime too. Qt legs fail discovery on import errors; shims are gone
# before another test module is loaded.
_runtime_module = _import_runtime() if _HAS_QT else None


class StartupImportHygieneTests(unittest.TestCase):
    # -.-.-.-
    def test_shims_restore_exact_state_after_success_or_import_failure(self):
        existing = types.ModuleType("google")
        for initial in ({}, {"google": existing, "google.genai": None}):
            for failure in (None, ImportError("runtime import failed")):
                with self.subTest(existing=list(initial), failure=failure):
                    with patch.dict(sys.modules):
                        for name in HEAVY_IMPORTS:
                            sys.modules.pop(name, None)
                        sys.modules.update(initial)
                        before = {name: sys.modules.get(name, _MISSING) for name in HEAVY_IMPORTS}
                        runtime = types.ModuleType("main")

                        def import_module(name):
                            if name != "main":
                                raise ModuleNotFoundError(name, name=name)
                            for target in HEAVY_IMPORTS:
                                if target in initial:
                                    self.assertIs(sys.modules[target], initial[target])
                                else:
                                    self.assertIsInstance(sys.modules[target], types.ModuleType)
                            with self.assertRaisesRegex(AssertionError, "cannot execute provider"):
                                sys.modules["google.genai.types"].LiveConnectConfig()
                            if failure is not None:
                                raise failure
                            return runtime

                        with patch.object(importlib, "import_module", side_effect=import_module):
                            if failure is None:
                                self.assertIs(_import_runtime(), runtime)
                            else:
                                with self.assertRaisesRegex(ImportError, "runtime import failed"):
                                    _import_runtime()
                        for name, module in before.items():
                            self.assertIs(sys.modules.get(name, _MISSING), module, name)

    # -.-.-.-
    def test_missing_transitive_dependency_is_not_hidden(self):
        with patch.dict(sys.modules):
            sys.modules.pop("sounddevice", None)
            with patch.object(importlib, "import_module", side_effect=ModuleNotFoundError(
                "missing transitive dependency", name="_cffi_backend"
            )):
                with self.assertRaisesRegex(ModuleNotFoundError, "missing transitive dependency"):
                    _import_runtime()
            self.assertNotIn("sounddevice", sys.modules)


@unittest.skipUnless(_HAS_QT, "PyQt6 is not installed on this dependency-free leg")
class StartupBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # When Qt is installed, any runtime import failure must fail this gate.
        cls._runtime_cls = _runtime_module.AntonellaRuntime
        from ui import AntonellaUI

        # Keep this startup test non-interactive without contacting a provider.
        with patch("ui.get_gemini_key", return_value="synthetic-startup-test-key"):
            cls._ui = AntonellaUI()

    @classmethod
    def tearDownClass(cls):
        window = getattr(cls._ui, "_win", None)
        if window is not None:
            window.close()

    # -.-.-.-
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self._config_file = Path(temp_dir.name) / "api_keys.json"
        config_patch = patch.object(config, "_CONFIG_PATH", self._config_file)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        env_patch = patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    # -.-.-.-
    def test_construction_executes_config_binding_without_name_error(self):
        # Regression: __init__ calls get_config(); before the import fix
        # this raised NameError at startup.
        runtime = self._runtime_cls(self._ui)
        from core.voice_runtime import BargeInGate

        self.assertIsInstance(runtime._barge_gate, BargeInGate)

    def test_desktop_default_is_enabled_with_conservative_values(self):
        runtime = self._runtime_cls(self._ui)
        gate = runtime._barge_gate
        self.assertTrue(gate.enabled)
        self.assertEqual(gate.threshold, 900)
        self.assertEqual(gate.frames_above, 3)
        self.assertEqual(gate.cooldown_seconds, 2.0)

    def test_env_override_reaches_the_constructed_gate(self):
        self._config_file.write_text(json.dumps({
            "barge_in_enabled": True, "barge_in_threshold": 1000,
            "barge_in_frames": 4, "barge_in_cooldown": 3.0,
        }), encoding="utf-8")
        with patch.dict(os.environ, {
            "ANTONELLA_BARGE_IN_ENABLED": "false",
            "ANTONELLA_BARGE_IN_THRESHOLD": "1500",
            "ANTONELLA_BARGE_IN_FRAMES": "5",
            "ANTONELLA_BARGE_IN_COOLDOWN": "4.5",
        }):
            runtime = self._runtime_cls(self._ui)
        gate = runtime._barge_gate
        self.assertFalse(gate.enabled)
        self.assertEqual(gate.threshold, 1500)
        self.assertEqual(gate.frames_above, 5)
        self.assertEqual(gate.cooldown_seconds, 4.5)

    # -.-.-.-
    def test_config_override_reaches_the_constructed_gate(self):
        self._config_file.write_text(json.dumps({
            "barge_in_enabled": False, "barge_in_threshold": 1100,
            "barge_in_frames": 4, "barge_in_cooldown": 3.5,
        }), encoding="utf-8")
        gate = self._runtime_cls(self._ui)._barge_gate
        self.assertFalse(gate.enabled)
        self.assertEqual(gate.threshold, 1100)
        self.assertEqual(gate.frames_above, 4)
        self.assertEqual(gate.cooldown_seconds, 3.5)

    def test_typed_settings_are_the_source_of_truth(self):
        import inspect

        source = inspect.getsource(self._runtime_cls.__init__)
        self.assertIn("BargeInSettings.from_config", source)
        self.assertNotIn("enabled=bool(_cfg", source)
        with patch("main.get_config", wraps=config.get_config) as get_config:
            self._runtime_cls(self._ui)
        get_config.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
