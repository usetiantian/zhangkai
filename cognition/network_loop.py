"""HTTP perception connected to the complete cognitive and audit cycle."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable
from audit.chain import AuditChain
from cognition.loop import CycleResult, ShuiLoop
from contracts import Observation, Prediction
from goals import GoalCandidate
from perception import Capture
from perception.web import HttpAdapter
from values import ValueSet

class NetworkLoop:
    def __init__(
        self,
        state: Path,
        actions: Path,
        audit: Path,
        cache: Path,
        *,
        clock: Callable[[], datetime],
        values: ValueSet,
        candidates: tuple[GoalCandidate, ...],
        http_timeout_seconds: int,
        before_action: Callable[[Prediction, str], None] | None = None,
        after_action: Callable[[Prediction, str], None] | None = None,
        preferred_strategy: Callable[[], str | None] | None = None,
        audit_lock_timeout_seconds: float | None = None,
        audit_lock_poll_seconds: float | None = None,
    ) -> None:
        self.clock = clock
        self.http = HttpAdapter(
            cache,
            clock=clock,
            timeout_seconds=http_timeout_seconds,
        )
        self.cycle = ShuiLoop(
            state,
            actions,
            clock=clock,
            values=values,
            candidates=candidates,
            before_action=before_action,
            after_action=after_action,
            preferred_strategy=preferred_strategy,
        )
        self.world = self.cycle.world
        self.audit = AuditChain(
            audit,
            lock_timeout_seconds=audit_lock_timeout_seconds,
            lock_poll_seconds=audit_lock_poll_seconds,
        )

    def tick(self, url: str) -> CycleResult:
        remote = self.http.observe(url)
        if not remote.changed:
            return CycleResult("unchanged", "", "", False)
        identifier = hashlib.sha256(
            f"{url}\0{remote.content_hash}".encode()
        ).hexdigest()
        observation = Observation(
            id=f"obs-{identifier}",
            schema_version="1",
            created_at=remote.observed_at,
            source=url,
            observed_at=remote.observed_at,
            content_hash=remote.content_hash,
        )
        result = self.cycle.process(Capture(observation, remote.content))
        if result.status == "unchanged":
            return result
        self._audit(result, url)
        return result

    def _audit(self, result: CycleResult, url: str) -> None:
        now = self.clock()
        events = (
            ("observation.created", result.observation_id, {"source": url}),
            ("evidence.persisted", result.evidence_id, {}),
            ("plan.selected", result.plan_id, {}),
            ("prediction.recorded", result.prediction_id, {}),
            ("action.receipted", result.receipt_id, {}),
            (
                "verification.completed",
                result.verification_id,
                {"verified": result.receipt_verified},
            ),
        )
        cause_id = None
        for event_type, record_id, data in events:
            event_id = f"audit-{record_id}"
            self.audit.append(
                event_id,
                now,
                event_type,
                cause_id,
                "success",
                {"record_id": record_id, **data},
            )
            cause_id = event_id

    def audit_records(self) -> list[dict[str, object]]:
        if not self.audit.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.audit.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
