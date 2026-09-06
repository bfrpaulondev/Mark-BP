"""Supabase memory validator (ANT-276 PRIOR. 7).

One command to validate a real Supabase project end-to-end:

    python scripts/validate_supabase_memory.py

Steps: env check -> connectivity -> synthetic insert -> read-back ->
supersede -> cleanup -> report. Only SYNTHETIC data with a test owner
is created and ALWAYS cleaned up. The key is never printed. Missing
env -> NOT CONFIGURED (exit 0, no crash). Migrations are never applied
from here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENV_URL = "ANTONELLA_SUPABASE_URL"
ENV_KEY = "ANTONELLA_SUPABASE_KEY"
TEST_OWNER = "00000000-0000-0000-0000-00000000e2e1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="windows_e2e_reports/supabase_validation.json")
    args = parser.parse_args()

    url = os.environ.get(ENV_URL)
    key = os.environ.get(ENV_KEY)
    if not url or not key:
        print("NOT CONFIGURED — defina ANTONELLA_SUPABASE_URL e ANTONELLA_SUPABASE_KEY.")
        print("A key nunca é impressa.")
        return 0

    steps: list[dict] = []

    def step(name: str, fn) -> None:
        try:
            detail = fn() or {}
            steps.append({"step": name, "status": "PASS", **detail})
            print(f"PASS {name} {detail if detail else ''}")
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            steps.append(
                {"step": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
            )
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")

    client = None

    def connect():
        nonlocal client
        from memory.supabase_adapter import client_from_env

        client = client_from_env()
        return None

    created_ids: list[str] = []

    def insert_synthetic():
        payload = {
            "owner_id": TEST_OWNER,
            "type": "semantic",
            "state": "active",
            "title": "Antonella validation (synthetic)",
            "content": "memória sintética de validação — safe to delete",
            "summary": "",
            "source_kind": "runtime",
            "confidence": 0.5,
            "subject": "antonella-validation",
            "version": 1,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        response = client.table("memories").insert(payload).execute()
        rows = getattr(response, "data", None) or []
        if not rows:
            raise RuntimeError("insert returned no data (verificar RLS/migrations)")
        created_ids.append(rows[0]["id"])
        return {"id": rows[0]["id"]}

    def read_back():
        if not created_ids:
            raise RuntimeError("nothing inserted yet")
        record_id = created_ids[0]
        response = client.table("memories").select("*").eq("id", record_id).limit(1).execute()
        rows = getattr(response, "data", None) or []
        if not rows or rows[0]["content"] != "memória sintética de validação — safe to delete":
            raise RuntimeError("read-back mismatch")
        return None

    def supersede():
        if not created_ids:
            raise RuntimeError("nothing to supersede")
        response = (
            client.table("memories")
            .insert({
                "owner_id": TEST_OWNER,
                "type": "semantic",
                "state": "proposed",
                "title": "Antonella validation v2 (synthetic)",
                "content": "versão 2 sintética",
                "source_kind": "runtime",
                "confidence": 0.5,
                "subject": "antonella-validation",
                "version": 2,
                "supersedes_id": created_ids[0],
                "created_at": time.time(),
                "updated_at": time.time(),
            })
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if not rows:
            raise RuntimeError("supersede insert returned no data")
        created_ids.append(rows[0]["id"])
        return {"id": rows[0]["id"]}

    def owner_isolation_scan():
        # Informational with the service key (RLS bypasses it); with a
        # user key the RLS policies would make cross-owner rows vanish.
        response = (
            client.table("memories")
            .select("id")
            .eq("owner_id", TEST_OWNER)
            .eq("subject", "antonella-validation")
            .execute()
        )
        return {"rows": len(getattr(response, "data", None) or [])}

    def cleanup():
        removed = 0
        for target in list(created_ids):
            client.table("memories").delete().eq("id", target).execute()
            removed += 1
        return {"removed": removed}

    step("env", lambda: {"url_configured": bool(url)})
    step("connectivity", connect)
    if client is None:
        print("connectivity falhou — passos seguintes omitidos.")
    else:
        step("insert-synthetic", insert_synthetic)
        step("read-back", read_back)
        step("supersede", supersede)
        step("owner-isolation-scan", owner_isolation_scan)
        step("cleanup", cleanup)

    failed = [s for s in steps if s["status"] == "FAIL"]
    out = Path(__file__).resolve().parents[1] / "windows_e2e_reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "supabase_validation.json").write_text(
        json.dumps(steps, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nrelatório: {out / 'supabase_validation.json'}")
    print("NOT PRODUCTION VALIDATED — nunca aplicar migrations a partir daqui.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
