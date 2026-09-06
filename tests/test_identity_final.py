"""ANT-272 final identity regression (Principal follow-up on PR #64).

Scans every ACTIVE runtime surface for forbidden legacy product tokens,
case-insensitively:

    JARVIS / J.A.R.V.I.S / Tony Stark / Iron Man / MARK LI

The bare personal name "Mark" is intentionally NOT scanned — it is a
common personal name and a global ban would corrupt real user content.

Allowed occurrences (documented, not whitelisted product identity):
- identity PROHIBITION lines ("Do not call yourself JARVIS" /
  "Never call yourself JARVIS") in the system prompt / identity context;
- the token-free legacy-name mask in ui/__init__.py built from character
  codes (defense-in-depth against model output);
- this test file and other test/doc files asserting the ban.

Compatibility notes (documented in the PR): dashboard storage keys and
AES salt changed — remote devices require a ONE-TIME re-pair; TLS
certificate files renamed (regenerated on first dashboard start).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_TOKENS = ("jarvis", "j.a.r.v.i.s", "tony stark", "iron man", "mark li")

ACTIVE_SURFACES = (
    (ROOT / "main.py", "main.py"),
    (ROOT / "antonella.py", "antonella.py"),
    (ROOT / "core" / "prompt.txt", "core/prompt.txt"),
    (ROOT / "memory" / "config_manager.py", "memory/config_manager.py"),
)
ACTIVE_SURFACE_DIRS = (
    ROOT / "ui",
    ROOT / "dashboard",
    ROOT / "plugins",
)
# Surfaces where tokens may appear ONLY as an explicit prohibition of the
# legacy identity (system prompt / identity context).
PROHIBITION_PREFIXES = ("do not call yourself", "never call yourself")


def _active_files():
    for path, label in ACTIVE_SURFACES:
        yield path, label
    for base in ACTIVE_SURFACE_DIRS:
        for path in sorted(base.rglob("*")):
            if path.suffix in (".py", ".html", ".js", ".txt") and "__pycache__" not in str(path):
                yield path, str(path.relative_to(ROOT))


class IdentityFinalRegressionTests(unittest.TestCase):
    def test_no_forbidden_tokens_in_active_surfaces(self):
        for path, label in _active_files():
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                lowered = line.lower()
                for token in FORBIDDEN_TOKENS:
                    if token not in lowered:
                        continue
                    if "call yourself" in lowered:
                        continue  # documented prohibition of the legacy identity
                    with self.subTest(surface=label, line=line_no, token=token):
                        self.fail(f"forbidden token {token!r}: {line.strip()[:90]}")

    def test_ui_alias_is_removed_after_consumer_migration(self):
        ui_source = (ROOT / "ui" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("JarvisUI", ui_source)
        self.assertIn("class AntonellaUI", ui_source)

    def test_main_consumes_antonella_ui_only(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from ui import AntonellaUI", main_source)
        self.assertNotIn("JarvisUI", main_source)

    def test_legacy_mask_survives_without_literal_tokens(self):
        # The defense-in-depth mask must still exist, built from character
        # codes — no literal forbidden token in the source.
        ui_source = (ROOT / "ui" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("_LEGACY_IDENTITY_RE", ui_source)
        self.assertNotIn("jarvis", ui_source.lower())
        self.assertNotIn("mark li", ui_source.lower())

    def test_dashboard_protocol_migrated(self):
        for name in ("dashboard/static/app.html", "dashboard/static/login.html",
                     "dashboard/server.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(surface=name):
                self.assertNotIn("jarvis", text.lower())
                self.assertNotIn("JARVIS-DASHBOARD-v1", text)
        # The AES salt lives in app.html (client crypto) and server.py.
        for name in ("dashboard/static/app.html", "dashboard/server.py"):
            with self.subTest(surface=name):
                self.assertIn("ANTONELLA-DASHBOARD-v1", (ROOT / name).read_text(encoding="utf-8"))
        # Storage keys migrated on every surface that stores tokens.
        for name in ("dashboard/static/app.html", "dashboard/static/login.html"):
            with self.subTest(surface=name):
                self.assertIn("antonella_token", (ROOT / name).read_text(encoding="utf-8"))

    def test_legacy_icon_asset_is_removed(self):
        self.assertFalse((ROOT / "config" / "jarvis.ico").exists())


if __name__ == "__main__":
    unittest.main()
