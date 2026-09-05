from __future__ import annotations

import asyncio
import concurrent.futures
import http.client
import inspect
import json
from collections.abc import Mapping
from typing import Any


_DEFAULT_CDP_PORT = 9222
_MIN_CDP_PORT = 1024
_MAX_CDP_PORT = 65535
_MAX_HTTP_BYTES = 64 * 1024
_CHROMIUM_MARKERS = ("chrome/", "chromium/", "headlesschrome/", "edg/")
_SUPPORTED_BROWSER_HINTS = {"", "chrome", "edge", "brave", "opera", "operagx", "vivaldi", "chromium"}


# -.-.-.-
def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)


# -.-.-.-
def _result(
    action: str,
    *,
    ok: bool,
    delivered: bool,
    verified: bool,
    message: str = "",
    error: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "action": f"verified_desktop_control.{action}",
        "ok": bool(ok),
        "delivered": bool(delivered),
        "verified": bool(verified),
        "message": str(message or ""),
        "evidence": dict(evidence or {}),
    }
    if error:
        payload["error"] = str(error)
    return _json(payload)


# -.-.-.-
def _validate_port(value: Any) -> int:
    try:
        port = int(value if value not in (None, "") else _DEFAULT_CDP_PORT)
    except (TypeError, ValueError) as exc:
        raise ValueError("CDP port must be an integer.") from exc
    if port < _MIN_CDP_PORT or port > _MAX_CDP_PORT:
        raise ValueError(f"CDP port must be between {_MIN_CDP_PORT} and {_MAX_CDP_PORT}.")
    return port


# -.-.-.-
def _endpoint(port: int) -> str:
    return f"http://127.0.0.1:{int(port)}"


# -.-.-.-
def _http_json(port: int, path: str, *, timeout: float = 0.8) -> Any:
    """Read one bounded JSON response from the loopback debugger without redirects or scanning."""
    connection = http.client.HTTPConnection("127.0.0.1", int(port), timeout=max(0.1, min(timeout, 2.0)))
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"CDP endpoint returned HTTP {response.status}.")
        body = response.read(_MAX_HTTP_BYTES + 1)
        if len(body) > _MAX_HTTP_BYTES:
            raise RuntimeError("CDP response exceeded the local safety limit.")
        return json.loads(body.decode("utf-8"))
    finally:
        connection.close()


# -.-.-.-
def _is_chromium_probe(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    browser = str(payload.get("Browser") or "").casefold()
    return any(marker in browser for marker in _CHROMIUM_MARKERS)


# -.-.-.-
def _probe(port: int) -> dict[str, Any]:
    raw = _http_json(port, "/json/version")
    if not isinstance(raw, Mapping):
        raise RuntimeError("CDP version endpoint returned an invalid payload.")
    return {
        "browser": str(raw.get("Browser") or "")[:160],
        "protocol_version": str(raw.get("Protocol-Version") or "")[:40],
        "chromium": _is_chromium_probe(raw),
    }


# -.-.-.-
def _safe_connect_kwargs(connect_over_cdp) -> dict[str, Any] | None:
    """Require no_defaults support before attaching to a daily-driver browser."""
    try:
        parameters = inspect.signature(connect_over_cdp).parameters
    except (TypeError, ValueError):
        return None
    if "no_defaults" not in parameters:
        return None
    kwargs: dict[str, Any] = {
        "timeout": 3000,
        "no_defaults": True,
    }
    if "is_local" in parameters:
        kwargs["is_local"] = True
    return kwargs


# -.-.-.-
async def _page_record(page, index: int) -> dict[str, Any]:
    title = ""
    visibility = ""
    try:
        title = str(await page.title() or "")[:240]
    except Exception:
        pass
    try:
        visibility = str(await page.evaluate("() => document.visibilityState || ''") or "")[:40]
    except Exception:
        pass
    return {
        "index": int(index),
        "title": title,
        "url": str(getattr(page, "url", "") or "")[:1000],
        "visibility": visibility,
    }


# -.-.-.-
async def _collect_pages(browser) -> tuple[list[Any], list[dict[str, Any]]]:
    pages: list[Any] = []
    for context in list(getattr(browser, "contexts", []) or []):
        pages.extend(list(getattr(context, "pages", []) or []))
    records = [await _page_record(page, index) for index, page in enumerate(pages, start=1)]
    return pages, records


# -.-.-.-
def _select_record(
    records: list[Mapping[str, Any]],
    *,
    tab: Any = None,
    url: Any = None,
) -> tuple[int | None, str | None]:
    raw_tab = str(tab or "").strip()
    raw_url = str(url or "").strip().casefold()

    if raw_url:
        matches = [
            int(item.get("index") or 0)
            for item in records
            if raw_url in str(item.get("url") or "").casefold()
        ]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"No CDP tab matched URL fragment '{str(url)[:160]}'."
        return None, "Multiple CDP tabs matched that URL fragment; use a tab index or a more specific URL."

    if raw_tab.isdigit():
        index = int(raw_tab)
        if 1 <= index <= len(records):
            return index, None
        return None, f"CDP tab index must be between 1 and {len(records)}."

    if raw_tab:
        needle = raw_tab.casefold()
        matches = [
            int(item.get("index") or 0)
            for item in records
            if needle in str(item.get("title") or "").casefold()
        ]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"No CDP tab matched title fragment '{raw_tab[:160]}'."
        return None, "Multiple CDP tabs matched that title fragment; use a tab index or a more specific title."

    return None, "Specify a CDP tab index/title or URL fragment."


# -.-.-.-
async def _with_cdp(port: int, operation) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return _result(
            "browser_cdp",
            ok=False,
            delivered=False,
            verified=False,
            error="Playwright is unavailable; run the locked Antonella dependency sync before using CDP.",
        )

    endpoint = _endpoint(port)
    async with async_playwright() as playwright:
        connect = playwright.chromium.connect_over_cdp
        kwargs = _safe_connect_kwargs(connect)
        if kwargs is None:
            return _result(
                "browser_cdp",
                ok=False,
                delivered=False,
                verified=False,
                error=(
                    "This Playwright build cannot safely attach to the user's existing browser because "
                    "connect_over_cdp(no_defaults=True) is unavailable. Upgrade through the locked dependency workflow."
                ),
            )

        browser = None
        try:
            browser = await connect(endpoint, **kwargs)
            return await asyncio.wait_for(operation(browser), timeout=5.0)
        except Exception as exc:
            return _result(
                "browser_cdp",
                ok=False,
                delivered=False,
                verified=False,
                error=f"Could not complete the safe local CDP operation: {type(exc).__name__}",
                evidence={"endpoint": f"127.0.0.1:{port}"},
            )
        finally:
            if browser is not None:
                try:
                    await asyncio.wait_for(browser.close(), timeout=2.0)
                except Exception:
                    pass


# -.-.-.-
async def _list_tabs_operation(port: int, browser) -> str:
    _pages, records = await _collect_pages(browser)
    return _result(
        "browser_cdp_list_tabs",
        ok=True,
        delivered=True,
        verified=True,
        message=f"Read {len(records)} tab(s) from the explicitly enabled local CDP browser.",
        evidence={
            "endpoint": f"127.0.0.1:{port}",
            "tabs": records[:100],
            "truncated": len(records) > 100,
        },
    )


# -.-.-.-
async def _switch_tab_operation(port: int, browser, params: Mapping[str, Any]) -> str:
    pages, records = await _collect_pages(browser)
    index, error = _select_record(records, tab=params.get("tab"), url=params.get("url"))
    if error or index is None:
        return _result(
            "browser_cdp_switch_tab",
            ok=False,
            delivered=False,
            verified=False,
            error=error or "No CDP tab target was resolved.",
            evidence={"tab_count": len(records)},
        )

    target = pages[index - 1]
    before = records[index - 1]
    if str(before.get("visibility") or "").casefold() == "visible":
        return _result(
            "browser_cdp_switch_tab",
            ok=True,
            delivered=True,
            verified=True,
            message="The requested CDP tab was already active in its browser window.",
            evidence={"endpoint": f"127.0.0.1:{port}", "before": before, "after": before},
        )

    try:
        await target.bring_to_front()
    except Exception as exc:
        return _result(
            "browser_cdp_switch_tab",
            ok=False,
            delivered=False,
            verified=False,
            error=f"Could not activate the requested CDP tab: {type(exc).__name__}",
            evidence={"before": before},
        )

    await asyncio.sleep(0.12)
    after = await _page_record(target, index)
    verified = str(after.get("visibility") or "").casefold() == "visible"
    return _result(
        "browser_cdp_switch_tab",
        ok=verified,
        delivered=True,
        verified=verified,
        message=(
            "CDP tab activation was verified through the page visibility state."
            if verified
            else "The CDP activation request was delivered, but the target tab did not verify as visible."
        ),
        evidence={"endpoint": f"127.0.0.1:{port}", "before": before, "after": after},
    )


# -.-.-.-
def _run_async(coro, *, timeout: float = 10.0) -> str:
    """Run the short-lived CDP coroutine in its own thread/event loop without an implicit wait on timeout."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="AntonellaCDP")
    future = executor.submit(asyncio.run, coro)
    try:
        return future.result(timeout=max(1.0, min(timeout, 20.0)))
    except concurrent.futures.TimeoutError:
        cancelled = future.cancel()
        if cancelled and hasattr(coro, "close"):
            coro.close()
        return _result(
            "browser_cdp",
            ok=False,
            delivered=False,
            verified=False,
            error="Local CDP operation timed out.",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# -.-.-.-
def real_browser_cdp(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    browser_hint = str(params.get("browser") or "").strip().lower()
    if browser_hint not in _SUPPORTED_BROWSER_HINTS:
        return _result(
            action or "browser_cdp",
            ok=False,
            delivered=False,
            verified=False,
            error="CDP attachment is supported only for Chromium-based browsers; Firefox is not supported.",
        )

    try:
        port = _validate_port(params.get("cdp_port"))
    except ValueError as exc:
        return _result(action or "browser_cdp", ok=False, delivered=False, verified=False, error=str(exc))

    try:
        probe = _probe(port)
    except Exception as exc:
        return _result(
            action or "browser_cdp",
            ok=False,
            delivered=False,
            verified=False,
            error=(
                f"No explicitly enabled local CDP endpoint was verified on 127.0.0.1:{port} "
                f"({type(exc).__name__}). Antonella will not scan other ports or relaunch the browser."
            ),
            evidence={"endpoint": f"127.0.0.1:{port}"},
        )

    if not probe["chromium"]:
        return _result(
            action or "browser_cdp",
            ok=False,
            delivered=False,
            verified=False,
            error="The local debugging endpoint did not identify itself as a Chromium-based browser.",
            evidence={"endpoint": f"127.0.0.1:{port}", "probe": probe},
        )

    if action == "browser_cdp_status":
        return _result(
            action,
            ok=True,
            delivered=True,
            verified=True,
            message="Explicit local Chromium CDP endpoint verified.",
            evidence={"endpoint": f"127.0.0.1:{port}", "probe": probe},
        )

    if action == "browser_cdp_list_tabs":
        return _run_async(_with_cdp(port, lambda connected: _list_tabs_operation(port, connected)))

    if action == "browser_cdp_switch_tab":
        return _run_async(
            _with_cdp(port, lambda connected: _switch_tab_operation(port, connected, params))
        )

    return _result(
        action or "browser_cdp",
        ok=False,
        delivered=False,
        verified=False,
        error="Use browser_cdp_status, browser_cdp_list_tabs or browser_cdp_switch_tab.",
    )
