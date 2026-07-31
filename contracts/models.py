"""Versioned, immutable data contracts shared by Shui modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any, ClassVar


def _text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _aware(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _strings(name: str, value: tuple[str, ...], *, allow_empty: bool = False) -> None:
    if not isinstance(value, tuple) or (not value and not allow_empty):
        raise ValueError(f"{name} must be a non-empty tuple")
    for item in value:
        _text(name, item)


@dataclass(frozen=True, kw_only=True)
class Record:
    id: str
    schema_version: str
    created_at: datetime
    record_type: ClassVar[str]

    def __post_init__(self) -> None:
        _text("id", self.id)
        _text("schema_version", self.schema_version)
        _aware("created_at", self.created_at)

    def to_dict(self) -> dict[str, Any]:
        def encode(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Record):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        result = {field.name: encode(getattr(self, field.name)) for field in fields(self)}
        result["record_type"] = self.record_type
        return result


@dataclass(frozen=True, kw_only=True)
class Observation(Record):
    record_type: ClassVar[str] = "Observation"
    source: str
    observed_at: datetime
    content_hash: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("source", self.source)
        _aware("observed_at", self.observed_at)
        _text("content_hash", self.content_hash)


@dataclass(frozen=True, kw_only=True)
class Evidence(Record):
    record_type: ClassVar[str] = "Evidence"
    observation_id: str
    source_uri: str
    content_hash: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("observation_id", self.observation_id)
        _text("source_uri", self.source_uri)
        _text("content_hash", self.content_hash)


@dataclass(frozen=True, kw_only=True)
class Claim(Record):
    record_type: ClassVar[str] = "Claim"
    statement: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("statement", self.statement)
        _strings("evidence_ids", self.evidence_ids)


@dataclass(frozen=True, kw_only=True)
class Fact(Record):
    record_type: ClassVar[str] = "Fact"
    statement: str
    claim_ids: tuple[str, ...]
    valid_at: datetime

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("statement", self.statement)
        _strings("claim_ids", self.claim_ids)
        _aware("valid_at", self.valid_at)


@dataclass(frozen=True, kw_only=True)
class Goal(Record):
    record_type: ClassVar[str] = "Goal"
    description: str
    success_criteria: tuple[str, ...]
    status: str
    STATUSES: ClassVar[frozenset[str]] = frozenset(
        {"candidate", "active", "blocked", "completed", "abandoned"}
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("description", self.description)
        _strings("success_criteria", self.success_criteria)
        if self.status not in self.STATUSES:
            raise ValueError(f"invalid goal status: {self.status}")


@dataclass(frozen=True, kw_only=True)
class Step(Record):
    record_type: ClassVar[str] = "Step"
    capability: str
    expected_result: str
    recovery: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("capability", self.capability)
        _text("expected_result", self.expected_result)
        _text("recovery", self.recovery)


@dataclass(frozen=True, kw_only=True)
class Plan(Record):
    record_type: ClassVar[str] = "Plan"
    goal_id: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("goal_id", self.goal_id)
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ValueError("steps must be a non-empty tuple")
        if not all(isinstance(step, Step) for step in self.steps):
            raise ValueError("steps must contain Step records")


@dataclass(frozen=True, kw_only=True)
class ActionReceipt(Record):
    record_type: ClassVar[str] = "ActionReceipt"
    plan_id: str
    step_id: str
    status: str
    observed_change: str
    STATUSES: ClassVar[frozenset[str]] = frozenset({"succeeded", "failed", "unknown"})

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("plan_id", self.plan_id)
        _text("step_id", self.step_id)
        _text("observed_change", self.observed_change)
        if self.status not in self.STATUSES:
            raise ValueError(f"invalid receipt status: {self.status}")


@dataclass(frozen=True, kw_only=True)
class VerificationRecord(Record):
    record_type: ClassVar[str] = "VerificationRecord"
    receipt_id: str
    passed: bool
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("receipt_id", self.receipt_id)
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be bool")
        _strings("evidence_ids", self.evidence_ids)


@dataclass(frozen=True, kw_only=True)
class Experience(Record):
    record_type: ClassVar[str] = "Experience"
    statement: str
    event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("statement", self.statement)
        _strings("event_ids", self.event_ids)


@dataclass(frozen=True, kw_only=True)
class Hypothesis(Record):
    record_type: ClassVar[str] = "Hypothesis"
    statement: str
    evidence_ids: tuple[str, ...]
    falsification: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("statement", self.statement)
        _strings("evidence_ids", self.evidence_ids)
        _text("falsification", self.falsification)


@dataclass(frozen=True, kw_only=True)
class Unknown(Record):
    record_type: ClassVar[str] = "Unknown"
    question: str
    blocking_goal_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("question", self.question)
        _strings("blocking_goal_ids", self.blocking_goal_ids, allow_empty=True)


@dataclass(frozen=True, kw_only=True)
class Conflict(Record):
    record_type: ClassVar[str] = "Conflict"
    record_ids: tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _strings("record_ids", self.record_ids)
        if len(self.record_ids) < 2:
            raise ValueError("conflict requires at least two records")
        _text("description", self.description)


@dataclass(frozen=True, kw_only=True)
class Prediction(Record):
    record_type: ClassVar[str] = "Prediction"
    action_id: str
    expected_outcome: str
    verification_condition: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _text("action_id", self.action_id)
        _text("expected_outcome", self.expected_outcome)
        _text("verification_condition", self.verification_condition)


_TYPES: dict[str, type[Record]] = {
    cls.record_type: cls
    for cls in (
        Observation, Evidence, Claim, Fact, Goal, Step, Plan,
        ActionReceipt, VerificationRecord, Experience, Hypothesis, Unknown, Conflict, Prediction,
    )
}


def record_from_dict(data: dict[str, Any]) -> Record:
    if not isinstance(data, dict):
        raise ValueError("record must be a mapping")
    record_type = data.get("record_type")
    cls = _TYPES.get(record_type)
    if cls is None:
        raise ValueError(f"unknown record type: {record_type}")

    values = {key: value for key, value in data.items() if key != "record_type"}
    for name in ("created_at", "observed_at", "valid_at"):
        if name in values and isinstance(values[name], str):
            values[name] = datetime.fromisoformat(values[name])
    tuple_fields = (
        "evidence_ids", "claim_ids", "success_criteria", "event_ids",
        "blocking_goal_ids", "record_ids",
    )
    for name in tuple_fields:
        if name in values and isinstance(values[name], list):
            values[name] = tuple(values[name])
    if cls is Plan and isinstance(values.get("steps"), list):
        values["steps"] = tuple(record_from_dict(step) for step in values["steps"])
    return cls(**values)
