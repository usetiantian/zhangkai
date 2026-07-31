import tempfile
import unittest
from pathlib import Path

from checks import check_forbidden_imports, check_topology


class ProjectCheckTests(unittest.TestCase):
    def test_current_topology_is_complete(self):
        self.assertEqual(check_topology(Path.cwd()), [])

    def test_forbidden_third_party_import_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.py").write_text("import requests\n", encoding="utf-8")
            self.assertEqual(len(check_forbidden_imports(root)), 1)

    def test_standard_library_and_local_imports_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contracts").mkdir()
            (root / "ok.py").write_text(
                "import json\nfrom contracts import Goal\n", encoding="utf-8"
            )
            self.assertEqual(check_forbidden_imports(root), [])


if __name__ == "__main__":
    unittest.main()
