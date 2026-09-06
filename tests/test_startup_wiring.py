"""Startup binding regression (ANT-275 physical round 2).

The physical Windows round found `AntonellaRuntime.__init__` calling
`get_config()` while main.py imported only `get_gemini_key` — a
NameError that compileall and import-only CI could not catch because it
fires at CONSTRUCTION time, not at import time.

This module constructs the real runtime offscreen, executing the full
`__init__` binding path, and asserts the barge-in gate arrives from the
typed settings with the desktop default ENABLED. Requires PyQt6: runs
in the ui-widget CI job, skipped on dependency-free legs.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from ui import AntonellaUI  # proves the ui facade imports

    HAS_RUNTIME = True
except ImportError:  # pragma: no cover - dependency-free CI legs
    HAS_RUNTIME = False


@unittest.skipUnless(HAS_RUNTIME, "PyQt6 unavailable: dependency-free CI legs skip")
class StartupBindingTests(unittest.TestCase):
    def setUp(self):
        from main import AntonellaRuntime

        self._runtime_cls = AntonellaRuntime
        self._ui = AntonellaUI()

    def tearDown(self):
        # AntonellaUI facade has no close(); closing the underlying
        # window is enough to release the offscreen surface.
        window = getattr(self._ui, "_win", None)
        if window is not None:
            window.close()
        self._ui = None

    # -.-.-.-
    def _construct(self):
        return self._runtime_cls(self._ui)

    # -.-.-.-
    def test_construction_executes_config_binding_without_name_error(self):
        # Regression: __init__ calls get_config(); before the import fix
        # this raised NameError at startup.
        runtime = self._construct()
        from core.voice_runtime import BargeInGate

        self.assertIsInstance(runtime._barge_gate, BargeInGate)

    def test_desktop_default_is_enabled_with_conservative_values(self):
        runtime = self._construct()
        gate = runtime._barge_gate
        self.assertTrue(gate.enabled)
        self.assertEqual(gate.threshold, 900)
        self.assertEqual(gate.frames_above, 3)
        self.assertEqual(gate.cooldown_seconds, 2.0)

    def test_env_override_reaches_the_constructed_gate(self):
        os.environ["ANTONELLA_BARGE_IN_THRESHOLD"] = "1500"
        try:
            runtime = self._construct()
            self.assertEqual(runtime._barge_gate.threshold, 1500)
        finally:
            os.environ.pop("ANTONELLA_BARGE_IN_THRESHOLD", None)

    def test_typed_settings_are_the_source_of_truth(self):
        import inspect

        from main import AntonellaRuntime

        source = inspect.getsource(AntonellaRuntime.__init__)
        self.assertIn("BargeInSettings.from_config", source)
        self.assertNotIn("enabled=bool(_cfg", source)


if __name__ == "__main__":
    unittest.main()
