from __future__ import annotations

import asyncio
import concurrent.futures
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from actions.verified_browser_automation import (
    _element_state,
    _element_state_changed,
    _page_snapshot,
    _result,
    _state_changed,
)


_MUTATION_KEY = "__antonellaMutationState"
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# -.-.-.-
def _mutation_signal(baseline_count: int, event_count: int) -> bool:
    """Return whether post-action DOM mutations rise above nearby background noise."""
    baseline = max(0, int(baseline_count or 0))
    event = max(0, int(event_count or 0))
    if event <= 0:
        return False
    if baseline <= 1:
        return True
    return event >= baseline + max(2, baseline // 2)


# -.-.-.-
def _safe_filename(value: str | None) -> str:
    """Collapse a browser-supplied filename to a safe leaf name."""
    raw = Path(str(value or "download")).name
    cleaned = _INVALID_FILENAME.sub("_", raw).strip(" .")
    return (cleaned or "download")[:180]


# -.-.-.-
def _next_download_path(filename: str) -> Path:
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    candidate = downloads / safe_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem or "download"
    suffix = candidate.suffix
    for index in range(1, 1000):
        alternative = downloads / f"{stem} ({index}){suffix}"
        if not alternative.exists():
            return alternative
    return downloads / f"{stem}-{int(asyncio.get_event_loop().time() * 1000)}{suffix}"


# -.-.-.-
async def _reset_mutation_probe(page) -> int:
    try:
        value = await page.evaluate(
            f"""() => {{
                const key = '{_MUTATION_KEY}';
                const root = document.documentElement;
                if (!root) return 0;
                let state = window[key];
                if (!state || !state.observer) {{
                    state = {{ count: 0, observer: null }};
                    state.observer = new MutationObserver((records) => {{
                        state.count += records.length;
                    }});
                    state.observer.observe(root, {{
                        subtree: true,
                        childList: true,
                        attributes: true,
                        characterData: true
                    }});
                    window[key] = state;
                }}
                state.count = 0;
                return 0;
            }}"""
        )
        return int(value or 0)
    except Exception:
        return 0


# -.-.-.-
async def _read_mutation_probe(page) -> int:
    try:
        value = await page.evaluate(
            f"() => Math.min(Number(window['{_MUTATION_KEY}']?.count || 0), 100000)"
        )
        return max(0, int(value or 0))
    except Exception:
        return 0


# -.-.-.-
async def _resolve_locator(page, params: Mapping[str, Any], *, smart: bool = False):
    description = str(params.get("description") or "").strip()
    text = str(params.get("text") or "").strip()
    selector = str(params.get("selector") or "").strip()

    if selector:
        try:
            candidate = page.locator(selector).first
            if await candidate.count() > 0:
                return candidate, "selector"
        except Exception:
            pass

    if text:
        try:
            candidate = page.get_by_text(text, exact=False).first
            if await candidate.count() > 0:
                return candidate, "text"
        except Exception:
            pass

    if smart or description:
        for role in ("button", "link", "menuitem", "tab", "checkbox", "radio", "option"):
            try:
                candidate = page.get_by_role(role, name=description).first
                if await candidate.count() > 0:
                    return candidate, role
            except Exception:
                continue
        if description:
            try:
                candidate = page.get_by_text(description, exact=False).first
                if await candidate.count() > 0:
                    return candidate, "description"
            except Exception:
                pass

    return None, ""


# -.-.-.-
def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


# -.-.-.-
async def _verify_dom_click(session, params: Mapping[str, Any], *, smart: bool) -> str:
    page = await session._get_page()
    action = "smart_click" if smart else "click"
    locator, method = await _resolve_locator(page, params, smart=smart)
    if locator is None:
        return _result(action, ok=False, delivered=False, verified=False, error="No matching browser element was found.")

    settle_ms = _bounded_int(params.get("settle_ms"), 350, 50, 2000)
    baseline_ms = min(150, max(50, settle_ms // 3))
    before = await _page_snapshot(page)
    element_before = await _element_state(locator)

    await _reset_mutation_probe(page)
    await asyncio.sleep(baseline_ms / 1000)
    baseline_mutations = await _read_mutation_probe(page)
    await _reset_mutation_probe(page)

    try:
        await locator.click(timeout=8_000)
    except Exception as exc:
        return _result(action, ok=False, delivered=False, verified=False, error=f"Browser click failed: {exc}")

    await asyncio.sleep(settle_ms / 1000)
    event_mutations = await _read_mutation_probe(page)
    after = await _page_snapshot(page)
    element_after = await _element_state(locator)
    mutation_verified = _mutation_signal(baseline_mutations, event_mutations)
    observable = bool(
        _state_changed(before, after)
        or _element_state_changed(element_before, element_after)
        or mutation_verified
    )
    return _result(
        action,
        ok=observable,
        delivered=True,
        verified=observable,
        message=(
            "Browser click produced a verified structural or DOM state change."
            if observable
            else "The click was delivered, but no structural or above-noise DOM change was verified."
        ),
        evidence={
            "method": method,
            "before": before,
            "after": after,
            "element_before": element_before,
            "element_after": element_after,
            "baseline_mutations": baseline_mutations,
            "event_mutations": event_mutations,
            "mutation_signal": mutation_verified,
            "settle_ms": settle_ms,
        },
    )


# -.-.-.-
async def _verify_popup(session, params: Mapping[str, Any]) -> str:
    page = await session._get_page()
    locator, method = await _resolve_locator(page, params, smart=True)
    if locator is None:
        return _result("click_popup", ok=False, delivered=False, verified=False, error="No matching popup trigger was found.")

    timeout_ms = _bounded_int(params.get("timeout_ms"), 8000, 1000, 15000)
    before_count = len(page.context.pages)
    try:
        async with page.expect_popup(timeout=timeout_ms) as popup_info:
            await locator.click(timeout=timeout_ms)
        popup = await popup_info.value
    except Exception as exc:
        return _result(
            "click_popup",
            ok=False,
            delivered=True,
            verified=False,
            error=f"Popup was not verified after the click: {type(exc).__name__}",
            evidence={"method": method, "before_page_count": before_count},
        )

    try:
        await popup.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 5000))
    except Exception:
        pass
    after_count = len(page.context.pages)
    snapshot = await _page_snapshot(popup)
    popup_open = not popup.is_closed()
    verified = bool(popup_open and after_count >= before_count + 1)
    if verified and bool(params.get("follow_popup", True)):
        session._page = popup

    return _result(
        "click_popup",
        ok=verified,
        delivered=True,
        verified=verified,
        message=(
            "Popup creation was correlated with the click and verified."
            if verified
            else "A popup event was observed, but the resulting page state could not be verified."
        ),
        evidence={
            "method": method,
            "before_page_count": before_count,
            "after_page_count": after_count,
            "popup": snapshot,
            "followed": bool(verified and params.get("follow_popup", True)),
        },
    )


# -.-.-.-
async def _verify_download(session, params: Mapping[str, Any]) -> str:
    page = await session._get_page()
    locator, method = await _resolve_locator(page, params, smart=True)
    if locator is None:
        return _result("click_download", ok=False, delivered=False, verified=False, error="No matching download trigger was found.")

    timeout_ms = _bounded_int(params.get("timeout_ms"), 10000, 1000, 20000)
    try:
        async with page.expect_download(timeout=timeout_ms) as download_info:
            await locator.click(timeout=timeout_ms)
        download = await download_info.value
    except Exception as exc:
        return _result(
            "click_download",
            ok=False,
            delivered=True,
            verified=False,
            error=f"Download event was not verified after the click: {type(exc).__name__}",
            evidence={"method": method},
        )

    try:
        failure = await download.failure()
    except Exception:
        failure = None
    suggested = _safe_filename(getattr(download, "suggested_filename", "download"))
    extension = Path(suggested).suffix.lower()[:20]
    save_requested = bool(params.get("save_download", False))
    saved = False
    size_bytes: int | None = None

    if save_requested and failure is None:
        try:
            destination = _next_download_path(suggested)
            await download.save_as(str(destination))
            saved = destination.exists()
            if saved:
                size_bytes = int(destination.stat().st_size)
        except Exception as exc:
            return _result(
                "click_download",
                ok=False,
                delivered=True,
                verified=False,
                error=f"Download started but could not be persisted safely: {type(exc).__name__}",
                evidence={"method": method, "download_event": True, "saved": False, "extension": extension},
            )

    verified = bool(failure is None and (not save_requested or saved))
    return _result(
        "click_download",
        ok=verified,
        delivered=True,
        verified=verified,
        message=(
            "Download event verified and file persisted in Downloads."
            if verified and save_requested
            else "Download event verified; persistence was not requested."
            if verified
            else "A download event occurred, but completion could not be verified."
        ),
        evidence={
            "method": method,
            "download_event": True,
            "save_requested": save_requested,
            "saved": saved,
            "extension": extension,
            "size_bytes": size_bytes,
            "download_failure": bool(failure),
        },
    )


# -.-.-.-
async def _dispatch(session, action: str, params: Mapping[str, Any]) -> str:
    if action == "click":
        return await _verify_dom_click(session, params, smart=False)
    if action == "smart_click":
        return await _verify_dom_click(session, params, smart=True)
    if action == "click_popup":
        return await _verify_popup(session, params)
    if action == "click_download":
        return await _verify_download(session, params)
    return _result(action, ok=False, delivered=False, verified=False, error="Unsupported browser event action.")


# -.-.-.-
def verified_browser_event_action(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    browser = str(params.get("browser") or "").strip().lower() or None
    try:
        from actions.browser_control import _registry

        session = _registry.get(browser)
        result = session.run(_dispatch(session, action, params), timeout=60)
        if player:
            try:
                player.write_log(f"SYS: Verified browser event · {action}")
            except Exception:
                pass
        return result
    except concurrent.futures.TimeoutError:
        return _result(action, ok=False, delivered=False, verified=False, error="Verified browser event timed out after 60 seconds.")
    except Exception as exc:
        return _result(action, ok=False, delivered=False, verified=False, error=f"Verified browser event failed: {exc}")
