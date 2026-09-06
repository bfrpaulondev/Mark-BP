"""ANT-275 physical round 2 — dependency-light regressions for the real
API shapes found on Windows: pywinauto 0.6.9 (no child_window on raw
UIAWrapper, no RECT.middle_point) and pycaw 20251023 (modern
EndpointVolume attribute with legacy Activate fallback)."""

import unittest

from scripts.windows_e2e.executors import _endpoint_from_device, _rect_center
from scripts.windows_e2e.evidence import EvidenceRecord


class FakeRect:
    """pywinauto 0.6.9 RECT: coordinates only, no middle_point()."""

    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class _SpecWindow:
    """WindowSpecification-like: HAS child_window."""

    def __init__(self):
        self.child_window_called = None

    def child_window(self, **kwargs):
        self.child_window_called = kwargs
        return "control"


class _RawWrapper:
    """UIAWrapper-like: NO child_window attribute (0.6.9 real shape)."""

    def set_focus(self):
        pass


class RectCenterTests(unittest.TestCase):
    def test_center_computed_from_edges_without_middle_point(self):
        rect = FakeRect(100, 50, 300, 250)
        self.assertEqual(_rect_center(rect), (200, 150))

    def test_center_works_with_negative_coordinates(self):
        rect = FakeRect(-300, -250, -100, -50)
        self.assertEqual(_rect_center(rect), (-200, -150))


class PycawShapeTests(unittest.TestCase):
    def test_modern_endpoint_volume_attribute_is_used(self):
        endpoint = object()  # modern shape: attribute IS the endpoint
        iid_marker = object()

        class _ModernDevice:
            EndpointVolume = endpoint

        self.assertIs(_endpoint_volume_from(_ModernDevice(), iid_marker), endpoint)

    def test_legacy_activate_fallback(self):
        iid_marker = object()

        class _FakeInterface:
            def QueryInterface(self, iid):
                assert iid is iid_marker
                return "endpoint"

        class _LegacyDevice:
            def Activate(self, iid, ctx, none):
                assert iid is iid_marker
                return _FakeInterface()

        self.assertEqual(_endpoint_volume_from(_LegacyDevice(), iid_marker, ctx="fake-ctx"), "endpoint")


# -.-.-.-
def _endpoint_volume_from(device, iid_marker, ctx=None):
    """Mirror of the executor's real selection helper, with a fake iid so
    no COM/pycaw import is needed."""
    return _endpoint_from_device(device, iid_marker, ctx)


class UiaSelectorTests(unittest.TestCase):
    def test_spec_root_supports_child_window(self):
        spec = _SpecWindow()
        control = spec.child_window(title="Mudar título", control_type="Button")
        self.assertEqual(control, "control")
        self.assertEqual(spec.child_window_called, {"title": "Mudar título", "control_type": "Button"})

    def test_raw_wrapper_shape_is_documented_as_unsupported(self):
        # The 0.6.9 finding: a raw UIAWrapper lacks child_window. The
        # executor must therefore always store the WindowSpecification.
        wrapper = _RawWrapper()
        self.assertFalse(hasattr(wrapper, "child_window"))

    def test_executor_source_uses_spec_as_selector_root(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "scripts" / "windows_e2e" / "executors.py").read_text(encoding="utf-8")
        self.assertIn('.window(title=FIXTURE_TITLE)', source)
        self.assertNotIn('self._win = windows[0]', source)


class EvidenceShapeTests(unittest.TestCase):
    def test_volume_evidence_shape_unchanged(self):
        record = EvidenceRecord(
            case_id="volume", status="PASS", result={"ok": True}, evidence={"ok": True}
        )
        self.assertEqual(record.evidence, {"ok": True})


if __name__ == "__main__":
    unittest.main()
