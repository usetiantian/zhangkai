"""Deterministic implementation and wiring audit."""
from __future__ import annotations
import ast
import json
from pathlib import Path
from typing import Any, Iterable

MODULES = (
    "identity", "values", "goals", "contracts", "perception", "provenance",
    "world_model", "attention", "cognition", "capabilities", "experiments",
    "execution", "feedback", "learning", "evolution", "audit", "recovery",
)

def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".")[0])
    return result

def inspect_project(root: Path, modules: Iterable[str] = MODULES) -> dict[str, Any]:
    tests_dir = root / "tests"
    tests = list(tests_dir.glob("test_*.py")) if tests_dir.is_dir() else []
    production = [
        path for path in root.rglob("*.py")
        if "tests" not in path.parts and ".git" not in path.parts
    ]
    report: dict[str, Any] = {
        "_project": {
            "unified_entry": (root / "shui.py").is_file(),
            "production_files": len(production),
            "test_files": len(tests),
        }
    }
    for module in modules:
        directory = root / module
        implementations = (
            [path for path in directory.rglob("*.py") if path.name != "__init__.py"]
            if directory.is_dir() else []
        )
        report[module] = {
            "implementation_files": len(implementations),
            "test_references": sum(module in _imports(path) for path in tests),
            "production_references": sum(
                module in _imports(path)
                for path in production
                if module not in path.parts
            ),
        }
    return report

def markdown(report: dict[str, Any]) -> str:
    project = report["_project"]
    lines = [
        "# Shui implementation and wiring audit", "",
        f"Unified entry: **{project['unified_entry']}**",
        f"Production files: **{project['production_files']}**",
        f"Test files: **{project['test_files']}**", "",
        "| Module | Implementations | Test refs | Production refs |",
        "|---|---:|---:|---:|",
    ]
    for name, data in report.items():
        if name == "_project":
            continue
        lines.append(
            f"| {name} | {data['implementation_files']} | "
            f"{data['test_references']} | {data['production_references']} |"
        )
    return "\n".join(lines) + "\n"

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = inspect_project(root)
    output = root / "docs" / "IMPLEMENTATION_AUDIT.md"
    output.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
