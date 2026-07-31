"""Strict external configuration with no behavioral defaults."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from values import ValueWeight

class ConfigError(ValueError):
    """Raised when Shui configuration is incomplete or unsafe."""

@dataclass(frozen=True)
class IdentityConfig:
    name: str
    version: str
    mission: tuple[str, ...]

@dataclass(frozen=True)
class SourceConfig:
    id: str
    url: str
    protocol: str = "http"

@dataclass(frozen=True)
class GoalConfig:
    id: str
    description: str
    dependencies: tuple[str, ...]
    impacts: dict[str, float]


@dataclass(frozen=True)
class ScheduleConfig:
    fast_seconds: int
    slow_seconds: int

@dataclass(frozen=True)
class CapabilityConfig:
    enabled: tuple[str, ...]

@dataclass(frozen=True)
class PathConfig:
    state: Path
    actions: Path
    audit: Path

@dataclass(frozen=True)
class RuntimeSettings:
    http_timeout_seconds: int
    capability_timeout_seconds: int
    learning_min_samples: int
    soak_cycles: int
    audit_lock_timeout_seconds: float
    audit_lock_poll_seconds: float


@dataclass(frozen=True)
class CertificationConfig:
    tiers: tuple[dict, ...]


@dataclass(frozen=True)
class ShuiConfig:
    identity: IdentityConfig
    values: tuple[ValueWeight, ...]
    sources: tuple[SourceConfig, ...]
    goals: tuple[GoalConfig, ...]
    schedules: ScheduleConfig
    capabilities: CapabilityConfig
    paths: PathConfig
    runtime: RuntimeSettings
    certification: CertificationConfig

_SECRET_MARKERS = ("token", "secret", "password", "api_key", "apikey")

def _reject_secrets(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if any(marker in normalized for marker in _SECRET_MARKERS):
                raise ConfigError(f"secret-like field forbidden: {path}.{key}")
            _reject_secrets(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, f"{path}[{index}]")

def _exact(value: Any, fields: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must be an object")
    missing = fields - value.keys()
    unknown = value.keys() - fields
    if missing:
        raise ConfigError(f"{path} missing: {', '.join(sorted(missing))}")
    if unknown:
        raise ConfigError(f"{path} unknown: {', '.join(sorted(unknown))}")
    return value

def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{path} must be non-empty text")
    return value

def _positive_number(value: Any, path: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{path} must be a positive number")
    return value


def _positive_integer(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{path} must be a positive integer")
    return value

def load_config(path: Path) -> ShuiConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(str(error)) from error
    _reject_secrets(raw)
    sections = {
        "identity", "values", "sources", "goals", "schedules",
        "capabilities", "paths", "runtime", "certification",
    }
    root = _exact(raw, sections, "root")
    identity_raw = _exact(
        root["identity"], {"name", "version", "mission"}, "identity"
    )
    mission = identity_raw["mission"]
    if not isinstance(mission, list) or not mission:
        raise ConfigError("identity.mission must be a non-empty list")
    identity = IdentityConfig(
        _text(identity_raw["name"], "identity.name"),
        _text(identity_raw["version"], "identity.version"),
        tuple(_text(item, "identity.mission") for item in mission),
    )
    values = _load_values(root["values"])
    sources = _load_sources(root["sources"])
    goals = _load_goals(root["goals"])
    schedules = _load_schedules(root["schedules"])
    capabilities = _load_capabilities(root["capabilities"])
    paths = _load_paths(root["paths"], path.parent)
    runtime = _load_runtime(root["runtime"])
    certification = _load_certification(root["certification"])
    return ShuiConfig(
        identity, values, sources, goals, schedules, capabilities, paths, runtime, certification
    )


def _load_certification(raw: Any) -> CertificationConfig:
    spec = _exact(raw, {"tiers"}, "certification")
    tiers = spec["tiers"]
    if not isinstance(tiers, list) or not tiers:
        raise ConfigError("certification.tiers must be a non-empty list")
    result: list[dict] = []
    for index, item in enumerate(tiers):
        if not isinstance(item, dict):
            raise ConfigError(f"tier[{index}] must be an object")
        tier_name = _text(item.get("tier"), f"tier[{index}].tier")
        if tier_name not in {"cycles", "hours", "days"}:
            raise ConfigError(f"unknown tier: {tier_name}")
        for required in ("tier", "threshold"):
            if required not in item:
                raise ConfigError(f"tier[{index}] missing: {required}")
        if tier_name in {"hours", "days"} and "duration_seconds" not in item:
            raise ConfigError(f"tier[{index}] missing: duration_seconds")
        threshold = _positive_integer(item["threshold"], f"tier[{index}].threshold")
        if tier_name == "cycles":
            duration = 0
        else:
            duration = _positive_integer(
                item["duration_seconds"],
                f"tier[{index}].duration_seconds",
            )
        result.append({"tier": tier_name, "threshold": threshold, "duration_seconds": duration})
    return CertificationConfig(tuple(result))

def _load_values(raw: Any) -> tuple[ValueWeight, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("values must be a non-empty list")
    result = []
    for index, item in enumerate(raw):
        value = _exact(
            item, {"name", "weight", "source", "calibrated_at"}, f"values[{index}]"
        )
        try:
            result.append(
                ValueWeight(
                    _text(value["name"], "value.name"),
                    value["weight"],
                    _text(value["source"], "value.source"),
                    datetime.fromisoformat(value["calibrated_at"]),
                )
            )
        except (TypeError, ValueError) as error:
            raise ConfigError(str(error)) from error
    return tuple(result)

def _load_sources(raw: Any) -> tuple[SourceConfig, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("sources must be a non-empty list")
    result = []
    for index, item in enumerate(raw):
        source = _exact(item, {"id", "url", "protocol"}, f"sources[{index}]")
        protocol = _text(source["protocol"], "source.protocol")
        if protocol not in {"http", "github_api", "rss"}:
            raise ConfigError(f"source.protocol unsupported: {protocol}")
        result.append(
            SourceConfig(
                _text(source["id"], "source.id"),
                _text(source["url"], "source.url"),
                protocol,
            )
        )
    return tuple(result)

def _load_goals(raw: Any) -> tuple[GoalConfig, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("goals must be a non-empty list")
    result = []
    for index, item in enumerate(raw):
        goal = _exact(
            item,
            {"id", "description", "dependencies", "impacts"},
            f"goals[{index}]",
        )
        dependencies = goal["dependencies"]
        impacts = goal["impacts"]
        if not isinstance(dependencies, list):
            raise ConfigError("goal.dependencies must be a list")
        if not isinstance(impacts, dict) or not impacts:
            raise ConfigError("goal.impacts must be a non-empty object")
        if any(
            not isinstance(value, (int, float)) or not -1 <= value <= 1
            for value in impacts.values()
        ):
            raise ConfigError("goal impacts must be normalized numbers")
        result.append(
            GoalConfig(
                _text(goal["id"], "goal.id"),
                _text(goal["description"], "goal.description"),
                tuple(_text(value, "goal.dependency") for value in dependencies),
                dict(impacts),
            )
        )
    return tuple(result)


def _load_schedules(raw: Any) -> ScheduleConfig:
    value = _exact(raw, {"fast_seconds", "slow_seconds"}, "schedules")
    return ScheduleConfig(
        _positive_integer(value["fast_seconds"], "schedules.fast_seconds"),
        _positive_integer(value["slow_seconds"], "schedules.slow_seconds"),
    )

def _load_capabilities(raw: Any) -> CapabilityConfig:
    value = _exact(raw, {"enabled"}, "capabilities")
    enabled = value["enabled"]
    if not isinstance(enabled, list) or not enabled:
        raise ConfigError("capabilities.enabled must be a non-empty list")
    return CapabilityConfig(tuple(_text(item, "capability") for item in enabled))

def _load_paths(raw: Any, base: Path) -> PathConfig:
    value = _exact(raw, {"state", "actions", "audit"}, "paths")
    resolve = lambda item: (base / _text(item, "path")).resolve()
    return PathConfig(resolve(value["state"]), resolve(value["actions"]), resolve(value["audit"]))

def _load_runtime(raw: Any) -> RuntimeSettings:
    fields = {
        "http_timeout_seconds",
        "capability_timeout_seconds",
        "learning_min_samples",
        "soak_cycles",
        "audit_lock_timeout_seconds",
        "audit_lock_poll_seconds",
    }
    value = _exact(raw, fields, "runtime")
    return RuntimeSettings(
        _positive_integer(
            value["http_timeout_seconds"],
            "runtime.http_timeout_seconds",
        ),
        _positive_integer(
            value["capability_timeout_seconds"],
            "runtime.capability_timeout_seconds",
        ),
        _positive_integer(
            value["learning_min_samples"],
            "runtime.learning_min_samples",
        ),
        _positive_integer(value["soak_cycles"], "runtime.soak_cycles"),
        _positive_number(value["audit_lock_timeout_seconds"], "runtime.audit_lock_timeout_seconds"),
        _positive_number(value["audit_lock_poll_seconds"], "runtime.audit_lock_poll_seconds"),
    )
