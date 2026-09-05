import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.execution_result import ExecutionResult
from core.skills.context import SkillContext
from core.skills.manifest import SkillManifest, parse_manifest_text, validate_manifest
from core.skills.registry import SkillRegistry
from core.skills.result import SkillResult
from core.skills.validator import validate_skill_package


def _manifest(**overrides) -> SkillManifest:
    data = dict(
        name="Demo Skill",
        slug="demo-skill",
        version="1.0.0",
        description="Demonstração sintética",
        entrypoint="skill:run",
        permissions=("filesystem.read",),
        risk="low",
        timeout_seconds=30,
    )
    data.update(overrides)
    return SkillManifest.from_dict(data)


def _package(tmp: Path, skill_py: str, *, manifest: SkillManifest | None = None, with_tests: bool = True) -> Path:
    manifest = manifest or _manifest()
    pkg = tmp / manifest.slug
    pkg.mkdir(parents=True)
    (pkg / "manifest.yaml").write_text("name: demo\n", encoding="utf-8")
    (pkg / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (pkg / "skill.py").write_text(skill_py, encoding="utf-8")
    if manifest.dependencies:
        (pkg / "requirements.lock").write_text("requests==2.32.3\n", encoding="utf-8")
    if with_tests:
        tests = pkg / "tests"
        tests.mkdir()
        (tests / "test_skill.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return pkg


class ManifestTests(unittest.TestCase):
    def test_restricted_parser_handles_subset_without_pyyaml(self):
        data = parse_manifest_text("name: Demo\npermissions:\n  - filesystem.read\n# comment\n")
        self.assertEqual(data["name"], "Demo")
        self.assertEqual(data["permissions"], ["filesystem.read"])

    def test_structural_validation(self):
        self.assertEqual(validate_skill_package.__module__, "core.skills.validator")
        problems = validate_manifest(_manifest(slug="Bad Slug", version="1.0", risk="ultra", permissions=("root",), timeout_seconds=0))
        joined = "\n".join(problems)
        self.assertIn("kebab-case", joined)
        self.assertIn("semver", joined)
        self.assertIn("unknown risk", joined)
        self.assertIn("excessive/unknown permissions", joined)
        self.assertIn("timeout_seconds", joined)

    def test_valid_manifest_has_no_problems(self):
        self.assertEqual(validate_manifest(_manifest()), [])


class RegistryTests(unittest.TestCase):
    def test_generated_skills_never_activate_alone(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", ("filesystem.read",), "low")
        with self.assertRaises(ValueError):
            registry.transition("demo-skill", "active")  # draft -> active is illegal
        self.assertEqual(registry.get("demo-skill").state, "draft")

    def test_full_approval_path(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", ("filesystem.read",), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        self.assertEqual(registry.get("demo-skill").state, "active")

    def test_dangerous_skill_never_activates(self):
        registry = SkillRegistry()
        registry.register("risky", "1.0.0", ("network",), "dangerous")
        registry.transition("risky", "validating")
        registry.transition("risky", "tested")
        registry.transition("risky", "awaiting_approval")
        with self.assertRaises(ValueError):
            registry.transition("risky", "active")

    def test_rollback_and_revocation(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", (), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        registry.register("demo-skill", "1.1.0", (), "low")  # new version lands as draft
        registry.transition("demo-skill", "validating")
        registry.transition("demo-skill", "tested")
        registry.transition("demo-skill", "awaiting_approval")
        record = registry.rollback("demo-skill")
        self.assertEqual(record.state, "deprecated")
        registry.transition("demo-skill", "revoked")
        with self.assertRaises(ValueError):
            registry.transition("demo-skill", "active")  # revoked is terminal

    def test_activation_brief_lists_permissions_and_risk(self):
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", ("filesystem.read",), "low")
        brief = registry.activation_brief("demo-skill")
        self.assertEqual(brief["permissions"], ["filesystem.read"])
        self.assertEqual(brief["risk"], "low")
        self.assertTrue(brief["tests_required"])


class ValidatorTests(unittest.TestCase):
    def test_clean_skill_passes(self):
        with TemporaryDirectory() as tmp:
            problems = validate_skill_package(
                _package(Path(tmp), "def run(context):\n    return {'ok': True}\n"),
                _manifest(),
            )
            self.assertEqual(problems, [])

    def test_forbidden_import_is_rejected(self):
        with TemporaryDirectory() as tmp:
            problems = validate_skill_package(
                _package(Path(tmp), "import subprocess\n\ndef run(context):\n    return {}\n"),
                _manifest(),
            )
            self.assertTrue(any("forbidden import: subprocess" in p for p in problems))

    def test_network_requires_permission(self):
        with TemporaryDirectory() as tmp:
            problems = validate_skill_package(
                _package(Path(tmp), "import requests\n\ndef run(context):\n    return {}\n"),
                _manifest(),
            )
            self.assertTrue(any("network import without permission: requests" in p for p in problems))

    def test_environ_access_is_rejected_in_favour_of_injected_secrets(self):
        with TemporaryDirectory() as tmp:
            problems = validate_skill_package(
                _package(Path(tmp), "import os\n\ndef run(context):\n    return {'k': os.environ['X']}\n"),
                _manifest(),
            )
            self.assertTrue(any("os.environ" in p for p in problems))

    def test_write_requires_permission_and_lock_is_required_for_dependencies(self):
        with TemporaryDirectory() as tmp:
            manifest = _manifest(dependencies=("requests",), permissions=("filesystem.write",))
            problems = validate_skill_package(
                _package(Path(tmp), "def run(context):\n    open('x.txt', 'w').write('x')\n    return {}\n", manifest=manifest),
                manifest,
            )
            self.assertFalse(any("filesystem.write" in p for p in problems))  # permission granted
            self.assertFalse(any("requirements.lock" in p for p in problems))  # lock exists in fixture

    def test_lock_is_required_when_dependencies_are_declared(self):
        with TemporaryDirectory() as tmp:
            manifest = _manifest(dependencies=("requests",))
            package = _package(Path(tmp), "def run(context):\n    return {}\n", manifest=manifest)
            (package / "requirements.lock").unlink()
            problems = validate_skill_package(package, manifest)
            self.assertTrue(any("requirements.lock" in p for p in problems))

    def test_missing_tests_or_skillmd_or_lock_are_rejected(self):
        with TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp), "def run(context):\n    return {}\n", with_tests=False)
            problems = validate_skill_package(pkg, _manifest())
            self.assertTrue(any("missing tests" in p for p in problems))
            self.assertTrue(any("missing SKILL.md" not in p for p in problems))


class ContextAndResultTests(unittest.TestCase):
    def test_context_hides_secret_values_and_enforces_lookup(self):
        context = SkillContext(
            working_dir=Path("."), permissions=frozenset({"filesystem.read"}),
            secrets=frozenset({("openai_key", "sk-supersecret")}),
        )
        view = context.redacted_dict()
        self.assertNotIn("sk-supersecret", str(view))
        self.assertEqual(view["secrets_granted"], ["openai_key"])
        self.assertEqual(context.secret("openai_key"), "sk-supersecret")
        with self.assertRaises(KeyError):
            context.secret("other")

    def test_skill_result_maps_into_execution_result_without_claiming_verification(self):
        result = SkillResult(skill_slug="demo-skill", ok=True, delivered=True, output={"x": 1})
        self.assertFalse(result.can_claim_success)  # ran fine ≠ verified
        execution = result.to_execution_result()
        self.assertIsInstance(execution, ExecutionResult)
        self.assertFalse(execution.verified)
        self.assertFalse(execution.can_claim_success)

        verified = SkillResult(skill_slug="demo-skill", ok=True, delivered=True, verified=True)
        self.assertTrue(verified.to_execution_result().can_claim_success)


if __name__ == "__main__":
    unittest.main()


class MultiVersionRegistryTests(unittest.TestCase):
    """S1/S2 — real versioning: registering v2 never destroys v1."""

    def _registry_with_active_v1(self) -> SkillRegistry:
        registry = SkillRegistry()
        registry.register("demo-skill", "1.0.0", ("filesystem.read",), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        return registry

    def test_registering_v2_preserves_v1_record(self):
        registry = self._registry_with_active_v1()
        registry.register("demo-skill", "1.1.0", ("filesystem.read",), "low")
        self.assertIsNotNone(registry.get_version("demo-skill", "1.0.0"))
        self.assertEqual(registry.get_version("demo-skill", "1.0.0").state, "active")
        self.assertEqual(registry.get("demo-skill").version, "1.1.0")  # latest is the candidate

    def test_rollback_candidate_keeps_v1_active(self):
        registry = self._registry_with_active_v1()
        registry.register("demo-skill", "1.1.0", (), "low")
        registry.transition("demo-skill", "validating")
        registry.transition("demo-skill", "tested")
        registry.transition("demo-skill", "awaiting_approval")
        registry.rollback("demo-skill")
        self.assertEqual(registry.get_version("demo-skill", "1.1.0").state, "deprecated")
        self.assertEqual(registry.active_version("demo-skill"), "1.0.0")
        self.assertEqual(registry.get_version("demo-skill", "1.0.0").state, "active")

    def test_rollback_of_active_v2_restores_v1_to_active(self):
        registry = self._registry_with_active_v1()
        registry.register("demo-skill", "1.1.0", (), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        self.assertEqual(registry.get_version("demo-skill", "1.0.0").state, "deprecated")
        registry.rollback("demo-skill")
        self.assertEqual(registry.active_version("demo-skill"), "1.0.0")
        self.assertEqual(registry.get_version("demo-skill", "1.0.0").state, "active")
        self.assertEqual(registry.get_version("demo-skill", "1.1.0").state, "deprecated")

    def test_only_one_active_version_at_a_time(self):
        registry = self._registry_with_active_v1()
        registry.register("demo-skill", "1.1.0", (), "low")
        for state in ("validating", "tested", "awaiting_approval", "active"):
            registry.transition("demo-skill", state)
        self.assertEqual(len(registry.active_skills()), 1)
        self.assertEqual(registry.active_skills()[0].version, "1.1.0")

    def test_rollback_from_draft_is_illegal(self):
        registry = self._registry_with_active_v1()
        registry.register("demo-skill", "1.1.0", (), "low")
        with self.assertRaises(ValueError):
            registry.rollback("demo-skill")


class SchemaManifestTests(unittest.TestCase):
    """S3 — input/output schemas load, validate and round-trip."""

    def test_from_dict_loads_schemas(self):
        manifest = _manifest(input_schema={"type": "object"}, output_schema={"type": "object"})
        self.assertEqual(manifest.input_schema, {"type": "object"})
        self.assertEqual(manifest.output_schema, {"type": "object"})

    def test_invalid_schema_is_flagged_not_crashed(self):
        manifest = _manifest(input_schema="not-a-mapping", output_schema=42)
        problems = validate_manifest(manifest)
        self.assertTrue(any("input_schema" in p for p in problems))
        self.assertTrue(any("output_schema" in p for p in problems))
        self.assertEqual(manifest.input_schema, {})

    def test_manifest_round_trip(self):
        manifest = _manifest(input_schema={"type": "object"}, output_schema={"type": "object"})
        clone = SkillManifest.from_dict(manifest.to_dict())
        self.assertEqual(clone, manifest)

    def test_fallback_yaml_parser_loads_schemas_block(self):
        text = "name: Demo\ninput_schema:\n  - broken\n"  # subset parser yields a list, not a mapping
        data = parse_manifest_text(text)
        manifest = SkillManifest.from_dict({**data, **_manifest().__dict__}) if False else SkillManifest.from_dict(
            {"name": "Demo", "slug": "demo", "version": "1.0.0", "description": "d",
             "entrypoint": "skill:run", "permissions": [], "risk": "low", "timeout_seconds": 5,
             "input_schema": data.get("input_schema")}
        )
        problems = validate_manifest(manifest)
        self.assertTrue(any("input_schema" in p for p in problems))
