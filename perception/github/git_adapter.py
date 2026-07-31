"""Read-only Git repository observation."""
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class GitState:
    is_repository: bool
    branch: str | None
    head: str | None
    modified: tuple[str, ...]
    untracked: tuple[str, ...]

class GitAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def observe(self) -> GitState:
        check = self._run("rev-parse", "--is-inside-work-tree")
        if check.returncode:
            return GitState(False, None, None, (), ())
        branch = self._run("branch", "--show-current").stdout.strip() or None
        head_result = self._run("rev-parse", "HEAD")
        head = head_result.stdout.strip() if head_result.returncode == 0 else None
        lines = self._run("status", "--porcelain").stdout.splitlines()
        modified: list[str] = []
        untracked: list[str] = []
        for line in lines:
            path = line[3:]
            target = untracked if line.startswith("??") else modified
            target.append(path)
        return GitState(True, branch, head, tuple(modified), tuple(untracked))
