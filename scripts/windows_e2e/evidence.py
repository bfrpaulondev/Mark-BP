"""Evidence bundle and physical test report generator (ANT-275 C4 + C10).

Evidence is bounded and technical: hashes, counts, booleans, state names,
timestamps and monitor indices. Never secrets, never raw content, never
screenshots unless explicitly configured and sanitised.

Statuses are honest and closed: SKIPPED is never reported as PASS.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

STATUSES = ("PASS", "FAIL", "SKIPPED", "NOT AVAILABLE", "NOT PHYSICALLY TESTED")

ALLOWED_EVIDENCE_KEYS = frozenset(
    {
        "hash",
        "length",
        "count",
        "ok",
        "state",
        "timestamp",
        "monitor_index",
        "window_title_hash",
        "duration_ms",
        "error_type",
        "retry_count",
    }
)

FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {
        "api_key",
        "password",
        "token",
        "clipboard",
        "screenshot_path",
        "prompt",
        "transcript",
        "cookie",
    }
)


def _sha256_short(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# -.-.-.-
def _markdown_cell(value: Any) -> str:
    text = str(value if value not in (None, "") else "—")
    return " ".join(text.replace("|", "/").split())[:180]


@dataclass
class EvidenceRecord:
    case_id: str
    status: str
    environment: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid evidence status: {self.status}")
        for key in list(self.evidence):
            if key in FORBIDDEN_EVIDENCE_KEYS or key not in ALLOWED_EVIDENCE_KEYS:
                self.evidence.pop(key, None)
        if "screenshot" in self.result:
            self.result.pop("screenshot")

    # -.-.-.-
    def window_title(self) -> str:
        return f"{self.case_id} :: {self.status}"


class EvidenceBundle:
    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []

    def add(self, record: EvidenceRecord) -> None:
        self._records.append(record)

    @property
    def records(self) -> list[EvidenceRecord]:
        return list(self._records)

    # -.-.-.-
    def to_json(self) -> str:
        return json.dumps(
            [
                {
                    "case_id": r.case_id,
                    "status": r.status,
                    "timestamp": r.timestamp,
                    "environment": r.environment,
                    "result": r.result,
                    "evidence": r.evidence,
                }
                for r in self._records
            ],
            indent=2,
        )

    # -.-.-.-
    def to_markdown(self) -> str:
        counts = {status: 0 for status in STATUSES}
        for record in self._records:
            counts[record.status] += 1
        lines = [
            "# Windows Physical E2E Report",
            "",
            "| Case | Status | Verified | Delivered | Error type | Error detail |",
            "|---|---|---|---|---|---|",
        ]
        for record in self._records:
            lines.append(
                f"| {_markdown_cell(record.case_id)} | {_markdown_cell(record.status)} "
                f"| {_markdown_cell(str(record.result.get('verified', '—')).lower())} "
                f"| {_markdown_cell(str(record.result.get('delivered', '—')).lower())} "
                f"| {_markdown_cell(record.result.get('error_type', '—'))} "
                f"| {_markdown_cell(record.result.get('error_detail', record.result.get('reason', '—')))} |"
            )
        lines.append("")
        lines.append("Summary: " + ", ".join(f"{status}: {count}" for status, count in counts.items()))
        lines.append("")
        lines.append("SKIPPED and NOT PHYSICALLY TESTED are never counted as PASS.")
        return "\n".join(lines)
