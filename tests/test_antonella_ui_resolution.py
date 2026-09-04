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
    def test_legacy_ui_module_remains_available_for_rollback(self):
        legacy = Path(__file__).resolve().parent.parent / "ui.py"
        new_ui = Path(__file__).resolve().parent.parent / "ui" / "__init__.py"

        self.assertTrue(legacy.is_file())
        self.assertTrue(new_ui.is_file())


if __name__ == "__main__":
    unittest.main()
