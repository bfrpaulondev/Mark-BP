"""Windows physical E2E runner (ANT-275 C1 + C10).

Discovers the matrix, gates every case on machine capabilities and on the
explicit physical gate, and produces an honest Markdown/JSON report.

Honesty rules:
- Without ``ANTONELLA_E2E_PHYSICAL=1`` every case is reported
  NOT PHYSICALLY TESTED (CI never fakes a physical run).
- Cases whose capabilities are missing are NOT AVAILABLE (missing listed).
- Executors are registered per case; a gated case without an executor is
  SKIPPED with the reason — never converted into PASS.
- Exit code is 1 only when a physically executed case FAILed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.windows_e2e import matrix as e2e_matrix  # noqa: E402
from scripts.windows_e2e.capability_probe import probe  # noqa: E402
from scripts.windows_e2e.evidence import EvidenceBundle, EvidenceRecord  # noqa: E402

# Executors are registered by physical sessions as they are implemented:
# {case_id: callable(capabilities) -> (result_dict, evidence_dict)}
EXECUTORS: dict[str, Any] = {}


def _requirement_missing(requirement: str, capabilities: dict) -> bool:
    """Evaluate a requirement against probed capabilities.

    Supports plain keys (truthy) and 'key>=number' comparisons.
    """
    if ">=" in requirement:
        key, _, raw = requirement.partition(">=")
        try:
            value = capabilities.get(key.strip())
            return value is None or int(value) < int(raw.strip())
        except (TypeError, ValueError):
            return True
    return not bool(capabilities.get(requirement))


def run(out_dir: Path, capabilities: dict | None = None) -> EvidenceBundle:
    capabilities = capabilities if capabilities is not None else probe()
    physical_gate = os.environ.get("ANTONELLA_E2E_PHYSICAL") == "1" and sys.platform == "win32"
    bundle = EvidenceBundle()

    for case in e2e_matrix.CASES:
        missing = [req for req in case.requirements if _requirement_missing(req, capabilities)]
        if missing:
            bundle.add(
                EvidenceRecord(
                    case_id=case.case_id,
                    status="NOT AVAILABLE",
                    environment={"missing": sorted(missing)},
                )
            )
            continue

        if not physical_gate:
            bundle.add(EvidenceRecord(case_id=case.case_id, status="NOT PHYSICALLY TESTED"))
            continue

        executor = EXECUTORS.get(case.case_id)
        if executor is None:
            bundle.add(
                EvidenceRecord(
                    case_id=case.case_id,
                    status="SKIPPED",
                    result={"error_type": "executor_not_implemented"},
                )
            )
            continue

        try:
            result, evidence = executor(capabilities)
            status = "PASS" if result.get("verified") and result.get("ok") else "FAIL"
            bundle.add(EvidenceRecord(case_id=case.case_id, status=status, result=result, evidence=evidence))
        except Exception as exc:  # noqa: BLE001 - a crash is a FAIL, never a pass
            bundle.add(
                EvidenceRecord(
                    case_id=case.case_id,
                    status="FAIL",
                    result={"ok": False, "delivered": False, "verified": False, "error_type": type(exc).__name__},
                )
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(bundle.to_markdown(), encoding="utf-8")
    (out_dir / "report.json").write_text(bundle.to_json(), encoding="utf-8")
    return bundle


def main() -> int:
    out_dir = Path(__file__).resolve().parents[2] / "windows_e2e_reports"
    bundle = run(out_dir)
    print(bundle.to_markdown())
    failed = any(record.status == "FAIL" for record in bundle.records)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
