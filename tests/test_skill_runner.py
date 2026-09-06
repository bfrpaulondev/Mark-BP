import os
import tempfile
import unittest
from pathlib import Path

from core.skills.manifest import SkillManifest
from core.skills.registry import SkillRegistry
from core.skills.runner import SkillRunner, explain_skill

SKILL_HAPPY = '''
def run(context):
    return {"ok": True, "echo": context["args"], "cwd": context["working_dir"]}
'''

SKILL_SECRET = '''
import os

def run(context):
    leaked = os.environ.get("ANTONELLA_TEST_KEY")
    secret = context["secrets"]["demo_key"]
    return {
        "ok": True,
        "secret": secret,
        "nested": {"message": "value=" + secret},
        "env_leak": leaked is not None,
    }
'''

SKILL_SECRET_CRASH = '''
def run(context):
    raise ValueError("failed with " + context["secrets"]["demo_key"])
'''

SKILL_SLEEP = '''
import time

def run(context):
    time.sleep(30)
    return {"ok": True}
'''


def _manifest(**overrides) -> SkillManifest:
    data = dict(
        name="Demo",
        slug="demo-skill",
        version="1.0.0",
        description="d",
        entrypoint="skill:run",
        permissions=("filesystem.write",),
        risk="low",
        timeout_seconds=15,
    )
    data.update(overrides)
    return SkillManifest.from_dict(data)


def _package(tmp: Path, source: str, manifest: SkillManifest) -> Path:
    pkg = tmp / manifest.slug
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "skill.py").write_text(source, encoding="utf-8")
    return pkg


class IsolatedRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.runner = SkillRunner(base_working_dir=self.tmp / "runs")
        os.environ["ANTONELLA_TEST_KEY"] = "injected-value"

    def tearDown(self):
        os.environ.pop("ANTONELLA_TEST_KEY", None)
        self._tmp.cleanup()

    def test_happy_path_returns_structured_result(self):
        pkg = _package(self.tmp, SKILL_HAPPY, _manifest())
        result = self.runner.run(_manifest(), pkg, {"hello": "antonella"}, {})
        self.assertTrue(result.ok)
        self.assertTrue(result.delivered)
        self.assertFalse(result.verified)
        self.assertEqual(result.output["echo"], {"hello": "antonella"})
        self.assertIsNotNone(result.duration_ms)

    def test_runner_creates_missing_base_working_dir(self):
        missing_base = self.tmp / "not-created-yet" / "runs"
        runner = SkillRunner(base_working_dir=missing_base)
        pkg = _package(self.tmp, SKILL_HAPPY, _manifest())

        result = runner.run(_manifest(), pkg, {}, {})

        self.assertTrue(result.ok)
        self.assertTrue(missing_base.is_dir())

    def test_working_dir_is_isolated_per_run(self):
        pkg = _package(self.tmp, SKILL_HAPPY, _manifest())
        result = self.runner.run(_manifest(), pkg, {}, {})
        cwd = Path(result.output["cwd"])
        self.assertTrue(str(cwd).startswith(str(self.runner._base)))

    def test_timeout_fails_closed(self):
        pkg = _package(self.tmp, SKILL_SLEEP, _manifest(timeout_seconds=1))
        result = self.runner.run(_manifest(timeout_seconds=1), pkg, {}, {})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "timeout")
        self.assertFalse(result.verified)

    def test_env_is_stripped_and_returned_secrets_are_redacted(self):
        pkg = _package(self.tmp, SKILL_SECRET, _manifest())
        result = self.runner.run(_manifest(), pkg, {}, {"demo_key": "sekret"})
        self.assertTrue(result.ok)
        self.assertEqual(result.output["secret"], "[REDACTED]")
        self.assertEqual(result.output["nested"]["message"], "value=[REDACTED]")
        self.assertFalse(result.output["env_leak"])
        self.assertNotIn("sekret", repr(result.output))

    def test_secret_in_crash_message_is_redacted(self):
        pkg = _package(self.tmp, SKILL_SECRET_CRASH, _manifest())
        result = self.runner.run(_manifest(), pkg, {}, {"demo_key": "sekret"})
        self.assertFalse(result.ok)
        self.assertIn("[REDACTED]", result.error or "")
        self.assertNotIn("sekret", result.error or "")

    def test_crashing_skill_returns_failure(self):
        pkg = _package(
            self.tmp,
            "raise ValueError('boom')\n\ndef run(context):\n    return {}\n",
            _manifest(),
        )
        result = self.runner.run(_manifest(), pkg, {}, {})
        self.assertFalse(result.ok)
        self.assertIn("boom", (result.error or ""))


class DiagnosticsTests(unittest.TestCase):
    def test_explains_unregistered_skill(self):
        reasons = explain_skill(SkillRegistry(), "ghost")
        self.assertTrue(any("not registered" in reason for reason in reasons))

    def test_explains_validation_and_state(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", (), "low")
        registry.transition("demo-skill", "validating")
        registry.transition("demo-skill", "tested")
        registry.transition("demo-skill", "awaiting_approval")
        reasons = explain_skill(
            registry,
            "demo-skill",
            validator_problems=["missing tests/test_*.py"],
            missing_capabilities=["network"],
        )
        joined = "\n".join(reasons)
        self.assertIn("missing tests", joined)
        self.assertIn("missing capabilities: network", joined)
        self.assertIn("awaiting human approval", joined)

    def test_explains_runner_failure(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", (), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        reasons = explain_skill(registry, "demo-skill", runner_error="timeout")
        self.assertTrue(any("timeout" in reason for reason in reasons))

    def test_no_blockers_when_active(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", (), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        self.assertEqual(explain_skill(registry, "demo-skill"), ["no known blockers"])


if __name__ == "__main__":
    unittest.main()
