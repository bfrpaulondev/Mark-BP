from __future__ import annotations

from pathlib import Path


def read_raw(path: str) -> str:
    with open(path, "r", encoding="utf-8", newline="") as stream:
        return stream.read()


def write_raw(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def replace_exact(path: str, old: str, new: str) -> None:
    text = read_raw(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    old_actual = old.replace("\n", nl)
    new_actual = new.replace("\n", nl)
    if old_actual not in text:
        raise SystemExit(f"expected block not found in {path}")
    write_raw(path, text.replace(old_actual, new_actual, 1))


# BLOCKER 1: one canonical typed settings source.
replace_exact(
    "config/settings.py",
    "    morning_brief_enabled: bool = True\n    plugins_enabled: dict[str, bool] = Field(default_factory=dict)\n",
    "    morning_brief_enabled: bool = True\n"
    "    barge_in_enabled: bool = True\n"
    "    barge_in_threshold: int = Field(default=900, ge=0)\n"
    "    barge_in_frames: int = Field(default=3, ge=1)\n"
    "    barge_in_cooldown: float = Field(default=2.0, ge=0.0)\n"
    "    plugins_enabled: dict[str, bool] = Field(default_factory=dict)\n",
)
replace_exact(
    "config/settings.py",
    "            \"morning_brief_enabled\": settings.morning_brief_enabled,\n            \"plugins_enabled\": settings.plugins_enabled,\n",
    "            \"morning_brief_enabled\": settings.morning_brief_enabled,\n"
    "            \"barge_in_enabled\": settings.barge_in_enabled,\n"
    "            \"barge_in_threshold\": settings.barge_in_threshold,\n"
    "            \"barge_in_frames\": settings.barge_in_frames,\n"
    "            \"barge_in_cooldown\": settings.barge_in_cooldown,\n"
    "            \"plugins_enabled\": settings.plugins_enabled,\n",
)

voice_path = "core/voice_runtime.py"
voice = read_raw(voice_path)
voice = voice.replace("from dataclasses import dataclass\n", "", 1)
marker = (
    "\n\n# ---------------------------------------------------------------------------\n"
    "# Barge-in typed settings (ANT-275 physical round 2)\n"
    "# ---------------------------------------------------------------------------\n"
)
if marker not in voice:
    raise SystemExit("BargeInSettings marker not found")
voice = voice.split(marker, 1)[0].rstrip() + "\n"
write_raw(voice_path, voice)

replace_exact(
    "main.py",
    "        from core.voice_runtime import BargeInSettings\n\n"
    "        _barge_settings          = BargeInSettings.from_config(get_config())\n"
    "        self._barge_gate          = BargeInGate(\n"
    "            enabled=_barge_settings.enabled,\n"
    "            threshold=_barge_settings.threshold,\n"
    "            frames_above=_barge_settings.frames_above,\n"
    "            cooldown_seconds=_barge_settings.cooldown_seconds,\n"
    "        )\n",
    "        self._barge_gate          = BargeInGate(\n"
    "            enabled=bool(_cfg[\"barge_in_enabled\"]),\n"
    "            threshold=int(_cfg[\"barge_in_threshold\"]),\n"
    "            frames_above=int(_cfg[\"barge_in_frames\"]),\n"
    "            cooldown_seconds=float(_cfg[\"barge_in_cooldown\"]),\n"
    "        )\n",
)

# BLOCKER 3: pycaw GUID and interface type are distinct.
replace_exact(
    "scripts/windows_e2e/executors.py",
    "    from comtypes import CLSCTX_ALL\n\n"
    "    devices = AudioUtilities.GetSpeakers()\n"
    "    return _endpoint_from_device(devices, IAudioEndpointVolume._iid_, CLSCTX_ALL)\n\n\n"
    "def _endpoint_from_device(device, iid, ctx):\n"
    "    \"\"\"pycaw 20251023 exposes AudioDevice.EndpointVolume directly; older\n"
    "    versions require the COM Activate + QueryInterface dance.\"\"\"\n"
    "    modern = getattr(device, \"EndpointVolume\", None)\n"
    "    if modern is not None:\n"
    "        return modern\n"
    "    interface = device.Activate(iid, ctx, None)\n"
    "    return interface.QueryInterface(iid)\n",
    "    devices = AudioUtilities.GetSpeakers()\n"
    "    return _endpoint_from_device(\n"
    "        devices, IAudioEndpointVolume._iid_, IAudioEndpointVolume, CLSCTX_ALL\n"
    "    )\n\n\n"
    "def _endpoint_from_device(device, iid, interface_type, ctx):\n"
    "    \"\"\"Return the endpoint for modern and legacy pycaw shapes.\n\n"
    "    Legacy activation uses the interface GUID for Activate(), then the\n"
    "    COM interface type for QueryInterface().\n"
    "    \"\"\"\n"
    "    modern = getattr(device, \"EndpointVolume\", None)\n"
    "    if modern is not None:\n"
    "        return modern\n"
    "    interface = device.Activate(iid, ctx, None)\n"
    "    return interface.QueryInterface(interface_type)\n",
)

# BLOCKER 4: the audit must not pretend to be scope-safe or whitelist Any.
audit = read_raw("tests/test_undefined_name_audit.py")
old_claim = (
    "This audit is the sound, dependency-free catch: for every active\n"
    "first-party module, any name LOADED that is never BOUND anywhere in\n"
    "that module (import/def/class/assign/loop/with/except/params) and is\n"
    "not a builtin is a guaranteed NameError at runtime — regardless of\n"
    "where the use sits (module level or function body).\n\n"
    "Soundness: no false positives for dynamic binding via globals()/eval\n"
    "only where those calls exist; such sites are allowed explicitly below.\n"
)
new_claim = (
    "This is a dependency-free project-wide guard for names that are loaded\n"
    "but never bound anywhere in a module. It is intentionally NOT scope-aware\n"
    "and can miss scope-specific binding errors, so the concrete get_config\n"
    "regression plus real AntonellaRuntime construction remain the primary\n"
    "startup gates.\n"
)
if old_claim not in audit:
    raise SystemExit("undefined-name audit claim block not found")
audit = audit.replace(old_claim, new_claim, 1)
old_implicit = 'IMPLICIT_MODULE_NAMES = frozenset({"__file__", "__name__", "__doc__", "__package__", "Any"})'
new_implicit = 'IMPLICIT_MODULE_NAMES = frozenset({"__file__", "__name__", "__doc__", "__package__"})'
if old_implicit not in audit:
    raise SystemExit("Any whitelist not found")
audit = audit.replace(old_implicit, new_implicit, 1)
write_raw("tests/test_undefined_name_audit.py", audit)

# Canonical settings regressions.
Path("tests/test_barge_in_settings.py").write_text('''from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import load_config, load_settings


BARGE_ENV = {
    "ANTONELLA_BARGE_IN_ENABLED",
    "ANTONELLA_BARGE_IN_THRESHOLD",
    "ANTONELLA_BARGE_IN_FRAMES",
    "ANTONELLA_BARGE_IN_COOLDOWN",
}


def _without_barge_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in BARGE_ENV}


class BargeInCanonicalSettingsTests(unittest.TestCase):
    def test_desktop_defaults_are_typed_and_enabled(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, _without_barge_env(), clear=True):
            settings = load_settings(Path(temp) / "missing.json")
        self.assertTrue(settings.barge_in_enabled)
        self.assertEqual(settings.barge_in_threshold, 900)
        self.assertEqual(settings.barge_in_frames, 3)
        self.assertEqual(settings.barge_in_cooldown, 2.0)

    def test_legacy_config_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, _without_barge_env(), clear=True):
            path = Path(temp) / "api_keys.json"
            path.write_text(json.dumps({
                "barge_in_enabled": False,
                "barge_in_threshold": 1200,
                "barge_in_frames": 4,
                "barge_in_cooldown": 2.5,
            }), encoding="utf-8")
            settings = load_settings(path)
        self.assertFalse(settings.barge_in_enabled)
        self.assertEqual(settings.barge_in_threshold, 1200)
        self.assertEqual(settings.barge_in_frames, 4)
        self.assertEqual(settings.barge_in_cooldown, 2.5)

    def test_environment_overrides_legacy_config(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "api_keys.json"
            path.write_text(json.dumps({
                "barge_in_enabled": False,
                "barge_in_threshold": 1200,
                "barge_in_frames": 4,
                "barge_in_cooldown": 2.5,
            }), encoding="utf-8")
            env = _without_barge_env()
            env.update({
                "ANTONELLA_BARGE_IN_ENABLED": "true",
                "ANTONELLA_BARGE_IN_THRESHOLD": "1500",
                "ANTONELLA_BARGE_IN_FRAMES": "5",
                "ANTONELLA_BARGE_IN_COOLDOWN": "3.0",
            })
            with patch.dict(os.environ, env, clear=True):
                settings = load_settings(path)
        self.assertTrue(settings.barge_in_enabled)
        self.assertEqual(settings.barge_in_threshold, 1500)
        self.assertEqual(settings.barge_in_frames, 5)
        self.assertEqual(settings.barge_in_cooldown, 3.0)

    def test_load_config_materializes_all_barge_in_fields(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, _without_barge_env(), clear=True):
            config = load_config(Path(temp) / "missing.json")
        self.assertEqual(
            {key: config[key] for key in (
                "barge_in_enabled",
                "barge_in_threshold",
                "barge_in_frames",
                "barge_in_cooldown",
            )},
            {
                "barge_in_enabled": True,
                "barge_in_threshold": 900,
                "barge_in_frames": 3,
                "barge_in_cooldown": 2.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# API-shape regressions reproduce the exact modern/legacy distinction.
Path("tests/test_physical_shapes.py").write_text('''"""ANT-275 physical round 2 compatibility regressions."""

import unittest

from scripts.windows_e2e.executors import _endpoint_from_device, _rect_center
from scripts.windows_e2e.evidence import EvidenceRecord


class FakeRect:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class _SpecWindow:
    def __init__(self):
        self.child_window_called = None

    def child_window(self, **kwargs):
        self.child_window_called = kwargs
        return "control"


class _RawWrapper:
    def set_focus(self):
        pass


class RectCenterTests(unittest.TestCase):
    def test_center_computed_from_edges_without_middle_point(self):
        self.assertEqual(_rect_center(FakeRect(100, 50, 300, 250)), (200, 150))

    def test_center_works_with_negative_coordinates(self):
        self.assertEqual(_rect_center(FakeRect(-300, -250, -100, -50)), (-200, -150))


class PycawShapeTests(unittest.TestCase):
    def test_modern_endpoint_volume_attribute_is_used_first(self):
        endpoint = object()

        class _ModernDevice:
            EndpointVolume = endpoint

            def Activate(self, *_args):
                raise AssertionError("legacy Activate must not run for modern pycaw")

        self.assertIs(_endpoint_from_device(_ModernDevice(), object(), object(), "ctx"), endpoint)

    def test_legacy_activate_uses_guid_but_query_interface_uses_type(self):
        iid_marker = object()
        interface_type = type("EndpointInterface", (), {})
        ctx_marker = object()
        activate_calls = []
        query_calls = []

        class _FakeInterface:
            def QueryInterface(self, requested_type):
                query_calls.append(requested_type)
                return "endpoint"

        class _LegacyDevice:
            def Activate(self, iid, ctx, none):
                activate_calls.append((iid, ctx, none))
                return _FakeInterface()

        result = _endpoint_from_device(_LegacyDevice(), iid_marker, interface_type, ctx_marker)
        self.assertEqual(result, "endpoint")
        self.assertEqual(activate_calls, [(iid_marker, ctx_marker, None)])
        self.assertEqual(query_calls, [interface_type])


class UiaSelectorTests(unittest.TestCase):
    def test_spec_root_supports_child_window(self):
        spec = _SpecWindow()
        control = spec.child_window(title="Mudar título", control_type="Button")
        self.assertEqual(control, "control")
        self.assertEqual(spec.child_window_called, {"title": "Mudar título", "control_type": "Button"})

    def test_raw_wrapper_shape_has_no_child_window(self):
        self.assertFalse(hasattr(_RawWrapper(), "child_window"))

    def test_executor_source_uses_spec_as_selector_root(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "windows_e2e" / "executors.py").read_text(encoding="utf-8")
        self.assertIn('.window(title=FIXTURE_TITLE)', source)
        self.assertNotIn('self._win = windows[0]', source)


class EvidenceShapeTests(unittest.TestCase):
    def test_volume_evidence_shape_unchanged(self):
        record = EvidenceRecord(case_id="volume", status="PASS", result={"ok": True}, evidence={"ok": True})
        self.assertEqual(record.evidence, {"ok": True})


if __name__ == "__main__":
    unittest.main()
'''.replace('import unittest\n\n', 'import unittest\nfrom pathlib import Path\n\n', 1), encoding="utf-8")

# BLOCKER 2: temporary shims restore the exact module family state.
Path("tests/test_startup_wiring.py").write_text('''"""Real runtime construction regression for ANT-275 startup wiring."""

from __future__ import annotations

import importlib
import importlib.machinery
import os
import sys
import types
import unittest
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HEAVY_IMPORTS = ("sounddevice", "google", "google.genai", "google.genai.types")
_MISSING = object()


def _belongs_to_family(name: str, requested: tuple[str, ...]) -> bool:
    roots = {item.split(".", 1)[0] for item in requested}
    return any(name == root or name.startswith(root + ".") for root in roots)


@contextmanager
def _temporary_dependency_shims(module_names: tuple[str, ...]):
    before = {
        name: module
        for name, module in sys.modules.items()
        if _belongs_to_family(name, module_names)
    }
    parent_attrs = {}
    for name in module_names:
        if "." not in name:
            continue
        parent_name, child = name.rsplit(".", 1)
        parent = sys.modules.get(parent_name)
        if parent is not None:
            parent_attrs[(parent_name, child)] = (
                hasattr(parent, child),
                getattr(parent, child, None),
            )
    try:
        for name in module_names:
            if name in sys.modules:
                continue
            try:
                importlib.import_module(name)
            except ImportError:
                stub = types.ModuleType(name)
                stub.__path__ = []
                stub.__spec__ = importlib.machinery.ModuleSpec(name, None)
                sys.modules[name] = stub
        yield
    finally:
        for name in list(sys.modules):
            if _belongs_to_family(name, module_names):
                sys.modules.pop(name, None)
        sys.modules.update(before)
        for (parent_name, child), (existed, value) in parent_attrs.items():
            parent = sys.modules.get(parent_name)
            if parent is None:
                continue
            if existed:
                setattr(parent, child, value)
            elif hasattr(parent, child):
                delattr(parent, child)


_HAS_RUNTIME = False
_RUNTIME_CLS = None
try:
    import PyQt6  # noqa: F401

    with _temporary_dependency_shims(HEAVY_IMPORTS):
        import main
        _RUNTIME_CLS = main.AntonellaRuntime
    _HAS_RUNTIME = True
except ImportError:
    _HAS_RUNTIME = False


@unittest.skipUnless(_HAS_RUNTIME, "runtime not importable on this leg")
class StartupBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ui import AntonellaUI
        cls._runtime_cls = _RUNTIME_CLS
        cls._ui = AntonellaUI()

    @classmethod
    def tearDownClass(cls):
        window = getattr(cls._ui, "_win", None)
        if window is not None:
            window.close()

    def test_construction_executes_config_binding_without_name_error(self):
        runtime = self._runtime_cls(self._ui)
        from core.voice_runtime import BargeInGate
        self.assertIsInstance(runtime._barge_gate, BargeInGate)

    def test_desktop_default_reaches_runtime_gate(self):
        runtime = self._runtime_cls(self._ui)
        gate = runtime._barge_gate
        self.assertTrue(gate.enabled)
        self.assertEqual(gate.threshold, 900)
        self.assertEqual(gate.frames_above, 3)
        self.assertEqual(gate.cooldown_seconds, 2.0)

    def test_env_override_reaches_runtime_gate(self):
        original = os.environ.get("ANTONELLA_BARGE_IN_THRESHOLD", _MISSING)
        os.environ["ANTONELLA_BARGE_IN_THRESHOLD"] = "1500"
        try:
            runtime = self._runtime_cls(self._ui)
            self.assertEqual(runtime._barge_gate.threshold, 1500)
        finally:
            if original is _MISSING:
                os.environ.pop("ANTONELLA_BARGE_IN_THRESHOLD", None)
            else:
                os.environ["ANTONELLA_BARGE_IN_THRESHOLD"] = original

    def test_runtime_consumes_one_canonical_config(self):
        import inspect
        source = inspect.getsource(self._runtime_cls.__init__)
        self.assertEqual(source.count("get_config()"), 1)
        self.assertNotIn("BargeInSettings", source)
        self.assertIn('_cfg["barge_in_enabled"]', source)


class ShimHygieneTests(unittest.TestCase):
    def test_temporary_shims_restore_exact_module_family_state(self):
        names = ("antonella_pr86_fakepkg", "antonella_pr86_fakepkg.child")
        before = {name: module for name, module in sys.modules.items() if _belongs_to_family(name, names)}
        with _temporary_dependency_shims(names):
            self.assertIn("antonella_pr86_fakepkg", sys.modules)
            self.assertIn("antonella_pr86_fakepkg.child", sys.modules)
        after = {name: module for name, module in sys.modules.items() if _belongs_to_family(name, names)}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# The temporary mechanism removes itself from the resulting PR diff.
for temporary in (
    Path(".github/workflows/pr86-principal-fix.yml"),
    Path(".github/workflows/pr86-principal-fix2.yml"),
    Path("scripts/pr86_principal_fix.py"),
):
    if temporary.exists():
        temporary.unlink()
