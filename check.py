"""Run all deterministic Shui project checks."""

from pathlib import Path

from checks import run


if __name__ == "__main__":
    raise SystemExit(run(Path(__file__).resolve().parent))
