from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.execution_result import ExecutionResult


_FILE_HASH_LIMIT = 8 * 1024 * 1024
_FILE_SAMPLE_SIZE = 256 * 1024
_DIR_ENTRY_LIMIT = 256

FILE_VERIFIABLE_ACTIONS = {
    "create_file",
    "create_folder",
    "delete",
    "move",
    "copy",
    "rename",
    "write",
    "organize_desktop",
}


# -.-.-.-
def _target_path(args: Mapping[str, Any]) -> Path | None:
    try:
        from actions.file_controller import _resolve_path

        base = _resolve_path(str(args.get("path") or "desktop"))
        name = str(args.get("name") or "").strip()
        return (base / name) if name else base
    except Exception:
        return None


# -.-.-.-
def _destination_path(args: Mapping[str, Any], source: Path | None) -> Path | None:
    destination = str(args.get("destination") or "").strip()
    if not destination:
        return None
    try:
        from actions.file_controller import _resolve_path

        target = _resolve_path(destination)
        if target.is_dir() and source is not None:
            return target / source.name
        return target
    except Exception:
        return None


# -.-.-.-
def _rename_path(args: Mapping[str, Any], source: Path | None) -> Path | None:
    new_name = str(args.get("new_name") or "").strip()
    if source is None or not new_name:
        return None
    return source.parent / new_name


# -.-.-.-
def _payload_digest(data: bytes) -> str:
    digest = hashlib.sha256()
    size = len(data)
    if size <= _FILE_HASH_LIMIT:
        digest.update(data)
    else:
        digest.update(data[:_FILE_SAMPLE_SIZE])
        digest.update(data[-_FILE_SAMPLE_SIZE:])
        digest.update(str(size).encode("ascii", errors="ignore"))
    return digest.hexdigest()


# -.-.-.-
def _file_digest(path: Path, size: int) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            if 0 <= size <= _FILE_HASH_LIMIT:
                for chunk in iter(lambda: handle.read(128 * 1024), b""):
                    digest.update(chunk)
            else:
                digest.update(handle.read(_FILE_SAMPLE_SIZE))
                handle.seek(max(0, size - _FILE_SAMPLE_SIZE))
                digest.update(handle.read(_FILE_SAMPLE_SIZE))
                digest.update(str(size).encode("ascii", errors="ignore"))
        return digest.hexdigest()
    except Exception:
        return ""


# -.-.-.-
def _file_ends_with(path: Path, suffix: bytes) -> bool:
    try:
        if not path.is_file():
            return False
        if not suffix:
            return True
        size = path.stat().st_size
        if size < len(suffix):
            return False
        with path.open("rb") as handle:
            handle.seek(size - len(suffix))
            return handle.read(len(suffix)) == suffix
    except Exception:
        return False


# -.-.-.-
def _directory_fingerprint(path: Path) -> tuple[str, int, bool]:
    entries: list[str] = []
    truncated = False
    try:
        for index, item in enumerate(sorted(path.rglob("*"), key=lambda value: str(value).casefold())):
            if index >= _DIR_ENTRY_LIMIT:
                truncated = True
                break
            try:
                relative = item.relative_to(path).as_posix()
                if item.is_dir():
                    entries.append(f"d:{relative}")
                elif item.is_file():
                    stat = item.stat()
                    entries.append(f"f:{relative}:{int(stat.st_size)}")
            except Exception:
                continue
    except Exception:
        return "", 0, False

    payload = "\n".join(entries).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest(), len(entries), truncated


# -.-.-.-
def _snapshot(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False, "resolvable": False}
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return {"exists": False, "resolvable": False}

    state: dict[str, Any] = {
        "exists": resolved.exists(),
        "resolvable": True,
        "name": resolved.name,
        "_path": str(resolved),
    }
    if not state["exists"]:
        return state

    try:
        stat = resolved.stat()
        state["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "other"
        state["size"] = int(stat.st_size)
        state["mtime_ns"] = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        if resolved.is_file():
            state["sha256"] = _file_digest(resolved, int(stat.st_size))
        elif resolved.is_dir():
            fingerprint, entries, truncated = _directory_fingerprint(resolved)
            state["tree_sha256"] = fingerprint
            state["entries"] = entries
            state["truncated"] = truncated
    except Exception:
        state["observable"] = False
    return state


# -.-.-.-
def _snapshot_from_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = str((state or {}).get("_path") or "").strip()
    return _snapshot(Path(raw)) if raw else {}


# -.-.-.-
def _path_from_state(state: Mapping[str, Any] | None) -> Path | None:
    raw = str((state or {}).get("_path") or "").strip()
    return Path(raw) if raw else None


# -.-.-.-
def _public(state: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in dict(state or {}).items()
        if not str(key).startswith("_")
    }


# -.-.-.-
def _same_object(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    if not before.get("exists") or not after.get("exists"):
        return False
    if before.get("kind") != after.get("kind"):
        return False
    if before.get("kind") == "file":
        if int(before.get("size") or -1) != int(after.get("size") or -2):
            return False
        before_hash = str(before.get("sha256") or "")
        after_hash = str(after.get("sha256") or "")
        return bool(before_hash and after_hash and before_hash == after_hash)
    if before.get("kind") == "directory":
        before_hash = str(before.get("tree_sha256") or "")
        after_hash = str(after.get("tree_sha256") or "")
        return bool(before_hash and after_hash and before_hash == after_hash)
    return False


# -.-.-.-
def capture_file_state(args: Mapping[str, Any] | None) -> dict[str, Any]:
    params = args or {}
    action = str(params.get("action") or "").strip().lower()
    source = _target_path(params)
    destination = None
    if action in {"move", "copy"}:
        destination = _destination_path(params, source)
    elif action == "rename":
        destination = _rename_path(params, source)

    state = {
        "action": action,
        "source": _snapshot(source),
        "destination": _snapshot(destination) if destination is not None else {},
    }
    if action == "organize_desktop":
        try:
            from actions.file_controller import _get_desktop

            state["source"] = _snapshot(_get_desktop())
        except Exception:
            pass
    return state


# -.-.-.-
def verify_file_postcondition(
    args: Mapping[str, Any] | None,
    *,
    before_state: Mapping[str, Any] | None,
    delivered: bool,
) -> ExecutionResult:
    params = args or {}
    action = str(params.get("action") or "").strip().lower()
    result_action = f"file_controller.{action or 'unknown'}"
    if not delivered:
        return ExecutionResult.failure(result_action, "Filesystem operation was not delivered.")

    before = dict(before_state or {})
    if not before:
        return ExecutionResult.unverified_delivery(
            result_action,
            message="Filesystem command was delivered, but no pre-action filesystem state was captured.",
        )

    before_source = before.get("source") if isinstance(before.get("source"), Mapping) else {}
    before_dest = before.get("destination") if isinstance(before.get("destination"), Mapping) else {}
    after_source = _snapshot_from_state(before_source)
    after_dest = _snapshot_from_state(before_dest)
    evidence = {
        "before_source": _public(before_source),
        "after_source": _public(after_source),
    }
    if before_dest:
        evidence["before_destination"] = _public(before_dest)
        evidence["after_destination"] = _public(after_dest)

    if action in {"create_file", "create_folder"}:
        expected_kind = "directory" if action == "create_folder" else "file"
        if after_source.get("exists") and after_source.get("kind") == expected_kind:
            if action == "create_file":
                expected_bytes = str(params.get("content") or "").encode("utf-8")
                evidence["expected_size"] = len(expected_bytes)
                actual_size = int(after_source.get("size") or 0)
                digest = str(after_source.get("sha256") or "")
                expected_digest = _payload_digest(expected_bytes)
                if actual_size != len(expected_bytes):
                    return ExecutionResult.failure(
                        result_action,
                        "Created file size did not match the requested content.",
                        delivered=True,
                        evidence=evidence,
                    )
                if not digest or digest != expected_digest:
                    return ExecutionResult.failure(
                        result_action,
                        "Created file content digest did not match the request.",
                        delivered=True,
                        evidence=evidence,
                    )
            return ExecutionResult.verified_success(result_action, evidence=evidence)

    elif action == "write":
        if not after_source.get("exists") or after_source.get("kind") != "file":
            return ExecutionResult.failure(
                result_action,
                "Target file was not present after write.",
                delivered=True,
                evidence=evidence,
            )
        content_bytes = str(params.get("content") or "").encode("utf-8")
        actual_size = int(after_source.get("size") or 0)
        target_path = _path_from_state(after_source)
        if bool(params.get("append", False)):
            before_size = int(before_source.get("size") or 0) if before_source.get("exists") else 0
            expected_size = before_size + len(content_bytes)
            evidence["expected_size"] = expected_size
            tail_matches = bool(target_path and _file_ends_with(target_path, content_bytes))
            evidence["appended_content_match"] = tail_matches
            if actual_size == expected_size and tail_matches:
                return ExecutionResult.verified_success(result_action, evidence=evidence)
        else:
            evidence["expected_size"] = len(content_bytes)
            digest = str(after_source.get("sha256") or "")
            expected_digest = _payload_digest(content_bytes)
            if actual_size == len(content_bytes) and digest == expected_digest:
                return ExecutionResult.verified_success(result_action, evidence=evidence)

    elif action == "delete":
        if before_source.get("exists") and not after_source.get("exists"):
            return ExecutionResult.verified_success(result_action, evidence=evidence)

    elif action in {"rename", "move"}:
        if before_source.get("exists") and not after_source.get("exists") and after_dest.get("exists"):
            if _same_object(before_source, after_dest):
                return ExecutionResult.verified_success(result_action, evidence=evidence)

    elif action == "copy":
        if before_source.get("exists") and after_source.get("exists") and after_dest.get("exists"):
            if _same_object(after_source, after_dest):
                return ExecutionResult.verified_success(result_action, evidence=evidence)

    elif action == "organize_desktop":
        before_fingerprint = str(before_source.get("tree_sha256") or "")
        after_fingerprint = str(after_source.get("tree_sha256") or "")
        if before_fingerprint and after_fingerprint and before_fingerprint != after_fingerprint:
            return ExecutionResult.verified_success(result_action, evidence=evidence)

    return ExecutionResult.unverified_delivery(
        result_action,
        evidence=evidence,
        message="Filesystem command was delivered, but the expected postcondition was not observed.",
    )
