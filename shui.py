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
from cognition.runtime import LearningRuntime
from evolution import CapabilityEvolution
from execution import TaskStore
from identity import Identity, IdentityStore
from recovery import RecoveryCoordinator
from world_model import WorldModel
from world_model.store import WorldModel as _WorldModel  # noqa: F401  (alias placeholder)


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
    for name in ("query", "trace", "explain"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--id", required=True)
    cert = commands.add_parser("cert")
    cert.add_argument("--config", type=Path, required=True)
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


def _cert(config: ShuiConfig) -> dict[str, object]:
    from experiments.certification import evaluate
    if not config.paths.audit.exists():
        return {
            "tiers": [
                {"tier": tier["tier"], "achieved": False, "reason": "no audit events"}
                for tier in config.certification.tiers
            ]
        }
    first_line = config.paths.audit.read_text(encoding="utf-8").splitlines()[0]
    started = datetime.fromisoformat(json.loads(first_line)["occurred_at"])
    now = datetime.now(timezone.utc)
    actual_seconds = (now - started).total_seconds()
    lines = config.paths.audit.read_text(encoding="utf-8").splitlines()
    actual_cycles = sum(
        1 for line in lines if json.loads(line).get("event_type") == "runtime.cycle.completed"
    )
    evidence_dir = config.paths.state / "certifications"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    counter = {"value": 0}

    def writer(body: str) -> str:
        counter["value"] += 1
        path = evidence_dir / f"{counter['value']}.json"
        path.write_text(body, encoding="utf-8")
        return str(path)

    results = evaluate(
        declared_tiers=list(config.certification.tiers),
        actual_cycles=actual_cycles,
        actual_seconds=actual_seconds,
        clock=lambda: now,
        evidence_writer=writer,
    )
    return {
        "started_at": started.isoformat(),
        "actual_cycles": actual_cycles,
        "actual_seconds": actual_seconds,
        "tiers": [
            {
                "tier": item.tier.value,
                "threshold": item.threshold,
                "duration_seconds": item.duration_seconds,
                "achieved": item.achieved,
                "actual_cycles": item.actual_cycles,
                "actual_seconds": item.actual_seconds,
                "granted_at": item.granted_at,
                "evidence_path": item.evidence_path,
            }
            for item in results
        ],
    }


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

def _real_cycle(config: ShuiConfig) -> dict[str, object]:
    runtime = LearningRuntime.from_config(
        config,
        clock=lambda: datetime.now(timezone.utc),
    )

    def process(source: str) -> str:
        status = runtime.tick(source).status
        if status == "failed":
            raise RuntimeError(f"source cycle failed: {source}")
        return status

    coordinator = RecoveryCoordinator(
        config.paths.state / "checkpoint.json",
        config.paths.state / "heartbeat.json",
        AuditChain(config.paths.audit),
        clock=lambda: datetime.now(timezone.utc),
        id_factory=lambda: f"runtime-{uuid.uuid4().hex}",
        processor=process,
    )
    report = coordinator.run_once(tuple(source.url for source in config.sources))
    return {"completed": report.completed, "failed": report.failed}


def _once(
    config: ShuiConfig,
    cycle_runner: Callable[[ShuiConfig], dict[str, object]],
) -> dict[str, object]:
    identity = _load_identity(config)
    TaskStore(config.paths.state / "tasks.db")
    CapabilityEvolution(config.paths.state / "capabilities")
    cycle = cycle_runner(config)
    event_id = f"runtime-{uuid.uuid4().hex}"
    AuditChain(config.paths.audit).append(
        event_id,
        datetime.now(timezone.utc),
        "runtime.cycle.completed",
        None,
        "success",
        {
            "identity": identity.name,
            "version": identity.version,
            "completed": cycle["completed"],
            "failed": cycle["failed"],
        },
    )
    return {"status": "completed", "event_id": event_id, **cycle}

def main(
    arguments: Sequence[str] | None = None,
    *,
    check_runner: Callable[[], int] | None = None,
    cycle_runner: Callable[[ShuiConfig], dict[str, object]] = _real_cycle,
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
        elif options.command == "query":
            result = _query(config, options)
        elif options.command == "trace":
            result = _trace(config, options.id)
        elif options.command == "explain":
            result = _explain(config, options.id)
        elif options.command == "cert":
            result = _cert(config)
        elif options.command == "once":
            result = _once(config, cycle_runner)
        else:
            if options.cycles is not None and options.cycles < 1:
                raise ConfigError("cycles must be positive")
            completed = 0
            while options.cycles is None or completed < options.cycles:
                _once(config, cycle_runner)
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
