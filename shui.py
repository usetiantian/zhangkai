"""Unified command-line entry for Shui."""
from __future__ import annotations
import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
from audit.chain import AuditChain
from checks import run as run_checks
from config import ConfigError, ShuiConfig, load_config
from evolution import CapabilityEvolution
from execution import TaskStore
from identity import Identity, IdentityStore
from world_model import WorldModel

ROOT = Path(__file__).resolve().parent

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shui")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    for name in ("once", "status"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--cycles", type=int)
    return parser

def _load_identity(config: ShuiConfig) -> Identity:
    store = IdentityStore(config.paths.state / "identity.db")
    expected = config.identity
    try:
        identity = store.latest()
    except LookupError:
        identity = Identity(
            expected.name,
            expected.version,
            expected.mission,
            datetime.now(timezone.utc),
        )
        store.save(identity)
    if (
        identity.name != expected.name
        or identity.version != expected.version
        or identity.mission != expected.mission
    ):
        raise ConfigError("stored identity conflicts with configured identity")
    return identity

def _status(config: ShuiConfig) -> dict[str, object]:
    identity = _load_identity(config)
    audit = AuditChain(config.paths.audit)
    world_path = config.paths.state / "world.db"
    world_records = len(WorldModel(world_path).all())
    audit_events = 0
    if config.paths.audit.exists():
        audit_events = len(config.paths.audit.read_text(encoding="utf-8").splitlines())
    task_counts = TaskStore(config.paths.state / "tasks.db").counts()
    evolved = CapabilityEvolution(config.paths.state / "capabilities").registered()
    return {
        "status": "ok",
        "identity": {"name": identity.name, "version": identity.version},
        "audit_valid": audit.verify(),
        "audit_events": audit_events,
        "world_records": world_records,
        "task_counts": task_counts,
        "configured_capabilities": list(config.capabilities.enabled),
        "evolved_capabilities": list(evolved),
    }

def _once(config: ShuiConfig) -> dict[str, object]:
    identity = _load_identity(config)
    TaskStore(config.paths.state / "tasks.db")
    CapabilityEvolution(config.paths.state / "capabilities")
    event_id = f"runtime-{uuid.uuid4().hex}"
    AuditChain(config.paths.audit).append(
        event_id,
        datetime.now(timezone.utc),
        "runtime.cycle.completed",
        None,
        "success",
        {"identity": identity.name, "version": identity.version},
    )
    return {"status": "completed", "event_id": event_id}

def main(
    arguments: Sequence[str] | None = None,
    *,
    check_runner: Callable[[], int] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    options = _parser().parse_args(arguments)
    try:
        if options.command == "check":
            code = (check_runner or (lambda: run_checks(ROOT)))()
            print(json.dumps({"status": "ok" if code == 0 else "failed"}))
            return code
        config = load_config(options.config)
        if options.command == "status":
            result = _status(config)
        elif options.command == "once":
            result = _once(config)
        else:
            if options.cycles is not None and options.cycles < 1:
                raise ConfigError("cycles must be positive")
            completed = 0
            while options.cycles is None or completed < options.cycles:
                _once(config)
                completed += 1
                if options.cycles is None or completed < options.cycles:
                    sleeper(config.schedules.fast_seconds)
            result = {"status": "completed", "cycles_completed": completed}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ConfigError, OSError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
