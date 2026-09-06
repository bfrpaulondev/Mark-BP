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

import importlib.machinery
import os
import sys
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HEAVY_IMPORTS = ("sounddevice", "google", "google.genai", "google.genai.types")

_HAS_QT = False
_HAS_RUNTIME = False
try:
    import PyQt6  # noqa: F401

    _HAS_QT = True
    try:
        import main  # noqa: F401  (real runtime; heavy deps may be shimmied below)

        _HAS_RUNTIME = True
    except ImportError:
        # Shim ONLY the missing heavy modules, import main, then drop the
        # stubs: main keeps its own references, sys.modules stays honest
        # for doctor's find_spec-based availability checks.
        for _name in HEAVY_IMPORTS:
            if _name in sys.modules:
                continue
            try:
                __import__(_name)
            except ImportError:
                stub = types.ModuleType(_name)
                stub.__path__ = []
                stub.__spec__ = importlib.machinery.ModuleSpec(_name, None)
                sys.modules[_name] = stub
        from main import AntonellaRuntime  # noqa: F401

        _HAS_RUNTIME = True
except ImportError:
    _HAS_QT = False  # dependency-free CI leg: everything skips


def _restore_sys_modules(saved: list[tuple[str, types.ModuleType | None]]) -> None:
    for name, module in saved:
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


@unittest.skipUnless(_HAS_RUNTIME, "runtime not importable on this leg")
class StartupBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import AntonellaRuntime

        cls._runtime_cls = AntonellaRuntime
        from ui import AntonellaUI

        cls._ui = AntonellaUI()

    @classmethod
    def tearDownClass(cls):
        window = getattr(cls._ui, "_win", None)
        if window is not None:
            window.close()

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
        os.environ["ANTONELLA_BARGE_IN_THRESHOLD"] = "1500"
        try:
            runtime = self._runtime_cls(self._ui)
            self.assertEqual(runtime._barge_gate.threshold, 1500)
        finally:
            os.environ.pop("ANTONELLA_BARGE_IN_THRESHOLD", None)

    def test_typed_settings_are_the_source_of_truth(self):
        import inspect

        source = inspect.getsource(self._runtime_cls.__init__)
        self.assertIn("BargeInSettings.from_config", source)
        self.assertNotIn("enabled=bool(_cfg", source)


if __name__ == "__main__":
    unittest.main()
