import importlib.util
import unittest
from pathlib import Path


class AntonellaUiResolutionTests(unittest.TestCase):
    # -.-.-.-
    def test_ui_import_resolves_to_antonella_package(self):
        spec = importlib.util.find_spec("ui")

        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.origin)
        self.assertIsNotNone(spec.submodule_search_locations)
        self.assertEqual(Path(spec.origin).as_posix().split("/")[-2:], ["ui", "__init__.py"])

    # -.-.-.-
    def test_legacy_ui_module_is_removed_after_b4_authorization(self):
        # B4 (authorized): the legacy module was proven unreachable
        # (package resolution + no entrypoint) and is now REMOVED.
        root = Path(__file__).resolve().parent.parent
        new_ui = root / "ui" / "__init__.py"

        self.assertFalse((root / "ui.py").exists())
        self.assertTrue(new_ui.is_file())

    # -.-.-.-
    def test_approved_reference_visual_contract_is_present(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "ui" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn('ANTONELLA_UI_IMPLEMENTATION = "reference-v2"', source)
        self.assertIn("class ParticleOrb", source)
        self.assertIn("Adaptive neural companion", source)
        self.assertIn("REGISTO", source)
        self.assertIn("Largar ficheiro", source)
        self.assertIn("Diz alguma coisa", source)
        self.assertIn("CORE STATUS", source)


if __name__ == "__main__":
    unittest.main()
