import ast
import unittest
from pathlib import Path


class ToolDispatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_path = Path(__file__).resolve().parents[1] / "main.py"
        cls.tree = ast.parse(cls.main_path.read_text(encoding="utf-8"))

    def test_tool_declarations_have_unique_valid_names(self):
        declarations = self._tool_declarations()
        names = [declaration["name"] for declaration in declarations]

        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(name.isidentifier(), name)

    def test_every_declared_tool_has_a_dispatch_branch(self):
        declared = {item["name"] for item in self._tool_declarations()}
        dispatched = set()

        execute_tool = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_tool"
        )
        for node in ast.walk(execute_tool):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not isinstance(node.left, ast.Name) or node.left.id != "name":
                continue
            if not isinstance(node.ops[0], ast.Eq) or len(node.comparators) != 1:
                continue
            comparator = node.comparators[0]
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                dispatched.add(comparator.value)

        self.assertEqual(declared - dispatched, set())

    def _tool_declarations(self):
        assignment = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TOOL_DECLARATIONS" for target in node.targets)
        )
        return ast.literal_eval(assignment.value)


if __name__ == "__main__":
    unittest.main()
