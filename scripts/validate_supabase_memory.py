"""Validate authenticated Supabase memory with synthetic rows only.

Requires ANTONELLA_SUPABASE_{URL,KEY,ACCESS_TOKEN,REFRESH_TOKEN}.
KEY must be publishable/legacy anon, never service-role. For an actual
cross-owner RLS check, provide a second distinct user with the same fields
under ANTONELLA_SUPABASE_TEST_B. No migrations are applied. Schema checks
cover the 0001/0005 exposed column contract, not migration history/indexes.
Every planned synthetic ID is tracked before writes and cleaned in finally.
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
from memory.domain import MemoryRecord, MemoryState, MemoryType
from memory.service import MemoryService
from memory.supabase_adapter import (ENV_FIELDS, SupabaseMemoryRepository,
    authenticated_owner_id, client_from_env, verify_memory_schema)


# -.-.-.-
def validate() -> dict:
    report = {"status": "NOT CONFIGURED", "steps": [], "rls": "NOT TESTED",
              "migration_history_and_indexes": "NOT TESTED"}
    if not any(name in os.environ for name in ENV_FIELDS):
        return report
    steps = report["steps"]
    cleanup_targets = []

    def step(name, action):
        try:
            action()
            steps.append({"step": name, "status": "PASS"})
        except Exception as error:
            # Provider text can contain tokens/URLs/row contents; never echo it.
            steps.append({"step": name, "status": "FAIL", "error_type": type(error).__name__})
            raise

    def prepare(prefix):
        client = client_from_env(prefix=prefix)
        owner = authenticated_owner_id(client)
        verify_memory_schema(client, owner)
        return client, owner, SupabaseMemoryRepository(client, owner_id=owner)

    def synthetic(client, owner, repo):
        now = time.time()
        row = MemoryRecord(id=str(uuid.uuid4()), owner_id=owner, type=MemoryType.SEMANTIC,
            title="Antonella validation (synthetic)", content="Synthetic validation only",
            source_kind="runtime", subject="validation-" + uuid.uuid4().hex,
            created_at=now, updated_at=now)
        cleanup_targets.append((client, owner, row.id))
        repo.save(row)
        if repo.get(row.id, owner).content != row.content:
            raise RuntimeError("Synthetic read-back mismatch")
        return row

    try:
        client, owner, repo = prepare("ANTONELLA_SUPABASE")
        steps.append({"step": "authenticated-session-and-schema-0001-0005", "status": "PASS"})
        row = synthetic(client, owner, repo)
        steps.append({"step": "insert-read-back", "status": "PASS"})
        service = MemoryService(repo)
        step("approve", lambda: service.approve(row.id, owner_id=owner))
        replacement = row.with_(id=str(uuid.uuid4()), version=2, supersedes_id=row.id,
                               content="Synthetic replacement", state=MemoryState.PROPOSED)
        cleanup_targets.append((client, owner, replacement.id))

        def supersede():
            repo.save(replacement)
            service.approve(replacement.id, owner_id=owner)
            if repo.get(row.id, owner).state != MemoryState.SUPERSEDED:
                raise RuntimeError("Supersession failed")
            if repo.get(replacement.id, owner).state != MemoryState.ACTIVE:
                raise RuntimeError("Replacement not active")
        step("supersede-read-back", supersede)

        def archive():
            service.archive(replacement.id, owner_id=owner)
            loaded = repo.get(replacement.id, owner)
            if loaded.state != MemoryState.ARCHIVED or loaded.archived_at is None:
                raise RuntimeError("Archive read-back failed")
        step("archive-read-back", archive)

        prefix = "ANTONELLA_SUPABASE_TEST_B"
        if any(f"{prefix}_{suffix}" in os.environ for suffix in ("URL", "KEY", "ACCESS_TOKEN", "REFRESH_TOKEN")):
            if os.environ.get(prefix + "_URL", "").rstrip('/') != os.environ.get(ENV_FIELDS[0], "").rstrip('/'):
                raise RuntimeError("RLS fixtures must use the same project")
            other_client, other_owner, other_repo = prepare(prefix)
            if owner == other_owner:
                raise RuntimeError("RLS fixtures require distinct authenticated users")
            other_row = synthetic(other_client, other_owner, other_repo)

            def cross_owner_checks(attacker, victim_owner, victim_row):
                # Use raw Data API calls: client-side owner filters are not an RLS proof.
                for operation in ("select", "update", "delete"):
                    query = attacker.table("memories")
                    if operation == "select": query = query.select("id")
                    elif operation == "update": query = query.update({"title": "RLS violation (synthetic)"})
                    else: query = query.delete()
                    response = query.eq("id", victim_row.id).execute()
                    if getattr(response, "data", None):
                        raise RuntimeError("Cross-owner access was allowed")
                forged_id = str(uuid.uuid4())
                victim_client = client if victim_owner == owner else other_client
                cleanup_targets.append((victim_client, victim_owner, forged_id))
                try:
                    attacker.table("memories").insert({"id": forged_id, "owner_id": victim_owner,
                        "type": "semantic", "title": "RLS synthetic", "content": "Synthetic only",
                        "source_kind": "runtime"}).execute()
                except Exception as error:
                    # Only an authorization rejection is evidence, never a timeout/schema error.
                    if str(getattr(error, "code", "")) != "42501":
                        raise RuntimeError("RLS insert rejection was not an authorization error") from None
                else:
                    raise RuntimeError("Cross-owner insert was allowed")

            step("memories-rls-A-to-B", lambda: cross_owner_checks(client, other_owner, other_row))
            step("memories-rls-B-to-A", lambda: cross_owner_checks(other_client, owner, row))
            # Verify denied updates/deletes did not silently affect either fixture.
            if repo.get(row.id, owner).title != row.title or other_repo.get(other_row.id, other_owner).title != other_row.title:
                raise RuntimeError("Cross-owner operations mutated a fixture")
            report["rls"] = "PASS: memories cross-owner CRUD with two authenticated users"
        else:
            steps.append({"step": "two-user-rls", "status": "NOT TESTED"})
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        if not steps or steps[-1]["status"] != "FAIL":
            steps.append({"step": "validation", "status": "FAIL", "error_type": type(error).__name__})
    finally:
        # Replacements are removed before their parents; failed writes are also tracked.
        for target_client, target_owner, target_id in reversed(cleanup_targets):
            try:
                target_client.table("memories").delete().eq("id", target_id).eq("owner_id", target_owner).execute()
                remaining = target_client.table("memories").select("id").eq("id", target_id).eq("owner_id", target_owner).execute()
                if getattr(remaining, "data", None):
                    raise RuntimeError("Synthetic cleanup did not remove the row")
                steps.append({"step": "cleanup-read-back", "status": "PASS"})
            except Exception as error:
                report["status"] = "FAIL"
                steps.append({"step": "cleanup-read-back", "status": "FAIL", "error_type": type(error).__name__})
    return report


# -.-.-.-
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="windows_e2e_reports/supabase_validation.json")
    args = parser.parse_args()
    report = validate()
    output = Path(args.output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        print("FAIL: validation report could not be written")
        return 1
    print(f"Supabase validation: {report['status']}; RLS: {report['rls']}")
    print("Migration history/indexes and child-table RLS: NOT TESTED; no migrations applied")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
