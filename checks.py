"""Deterministic project checks for Shui."""

from __future__ import annotations

import ast
import compileall
import subprocess
import sys
from pathlib import Path

from audit.quality import scan

REQUIRED_DIRECTORIES = frozenset({
    "identity", "values", "goals", "contracts", "perception", "provenance",
    "world_model", "attention", "cognition", "capabilities", "experiments",
    "execution", "feedback", "learning", "evolution", "audit", "recovery",
    "config", "data", "docs", "tests",
})
IGNORED_DIRECTORIES = frozenset({"data", ".git", "__pycache__"})


def check_topology(root: Path) -> list[str]:
    return [f"missing directory: {name}" for name in sorted(REQUIRED_DIRECTORIES)
            if not (root / name).is_dir()]


def check_forbidden_imports(root: Path) -> list[str]:
    local_modules = {path.name for path in root.iterdir() if path.is_dir()}
    allowed = set(sys.stdlib_module_names) | local_modules | {"checks"}
    errors: list[str] = []
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            errors.append(f"{path}: {error}")
            continue
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0
                     else [])
            for name in names:
                top = (name or "").split(".", 1)[0]
                if top and top not in allowed:
                    errors.append(f"{path}:{node.lineno}: forbidden import {top}")
    return errors


def run(root: Path) -> int:
    errors = check_topology(root) + check_forbidden_imports(root)
    errors.extend(
        f"{issue.path}:{issue.line}: {issue.kind} ({issue.detail})"
        for issue in scan(root)
    )
    if not compileall.compile_dir(root, quiet=1):
        errors.append("compile failed")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=root,
        check=False,
    )
    return result.returncode
