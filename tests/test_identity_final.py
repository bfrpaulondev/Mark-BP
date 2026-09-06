"""ANT-272 final identity regression (Principal follow-up on PR #64).

Scans every ACTIVE runtime surface for forbidden legacy product tokens,
case-insensitively:

    JARVIS / J.A.R.V.I.S / Tony Stark / Iron Man / MARK LI

The bare personal name "Mark" is intentionally NOT scanned — it is a
common personal name and a global ban would corrupt real user content.

Allowed occurrences are restricted to explicit identity-prohibition lines
inside the real system prompt / Antonella identity context. Tests/docs are
not active runtime surfaces and are intentionally outside this scan.

Compatibility notes (documented in the PR): dashboard storage keys and
AES salt changed — remote devices require a ONE-TIME re-pair; TLS
certificate files renamed (regenerated on first dashboard start).
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_TOKENS = ("jarvis", "j.a.r.v.i.s", "tony stark", "iron man", "mark li")
TEXT_SUFFIXES = (".py", ".html", ".js", ".txt", ".json", ".yaml", ".yml", ".toml")

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
    ROOT / "config",
)
PROHIBITION_SURFACES = frozenset({"antonella.py", "core/prompt.txt"})
PROHIBITION_PHRASES = ("do not call yourself", "never call yourself")


def _active_paths():
    seen: set[Path] = set()
    for path, label in ACTIVE_SURFACES:
        seen.add(path)
        yield path, label
    for base in ACTIVE_SURFACE_DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if "__pycache__" in path.parts or path in seen:
                continue
            yield path, str(path.relative_to(ROOT))


def _is_allowed_prohibition(label: str, lowered_line: str, token: str) -> bool:
    if label not in PROHIBITION_SURFACES:
        return False
    token_pos = lowered_line.find(token)
    if token_pos < 0:
        return False
    return any(
        (phrase_pos := lowered_line.find(phrase)) >= 0 and phrase_pos < token_pos
        for phrase in PROHIBITION_PHRASES
    )


class IdentityFinalRegressionTests(unittest.TestCase):
    def test_no_forbidden_tokens_in_active_surface_paths_or_text(self):
        for path, label in _active_paths():
            lowered_label = label.lower()
            for token in FORBIDDEN_TOKENS:
                with self.subTest(surface=label, token=token, location="path"):
                    self.assertNotIn(token, lowered_label)

            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue

            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                lowered = line.lower()
                for token in FORBIDDEN_TOKENS:
                    if token not in lowered:
                        continue
                    if _is_allowed_prohibition(label, lowered, token):
                        continue
                    with self.subTest(surface=label, line=line_no, token=token, location="text"):
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
        ui_source = (ROOT / "ui" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("_LEGACY_IDENTITY_RE", ui_source)
        self.assertNotIn("jarvis", ui_source.lower())
        self.assertNotIn("mark li", ui_source.lower())

    def test_dashboard_protocol_migrated(self):
        for name in (
            "dashboard/static/app.html",
            "dashboard/static/login.html",
            "dashboard/server.py",
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(surface=name):
                self.assertNotIn("jarvis", text.lower())
                self.assertNotIn("JARVIS-DASHBOARD-v1", text)

        for name in ("dashboard/static/app.html", "dashboard/server.py"):
            with self.subTest(surface=name):
                self.assertIn(
                    "ANTONELLA-DASHBOARD-v1",
                    (ROOT / name).read_text(encoding="utf-8"),
                )

        for name in ("dashboard/static/app.html", "dashboard/static/login.html"):
            with self.subTest(surface=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("antonella_token", text)
                self.assertIn("antonella_key", text)

    def test_legacy_icon_asset_is_removed(self):
        self.assertFalse((ROOT / "config" / "jarvis.ico").exists())


if __name__ == "__main__":
    unittest.main()
