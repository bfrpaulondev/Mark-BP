from __future__ import annotations

import asyncio
import concurrent.futures
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse


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
        "action": f"verified_browser_automation.{action}",
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
def _url_matches_target(actual: str, target: str) -> bool:
    actual_value = str(actual or "").strip()
    target_value = str(target or "").strip()
    if not actual_value or not target_value:
        return False
    try:
        actual_parsed = urlparse(actual_value)
        target_parsed = urlparse(target_value)
        if actual_parsed.scheme in {"http", "https"} and target_parsed.scheme in {"http", "https"}:
            if actual_parsed.netloc.casefold() != target_parsed.netloc.casefold():
                return False
            target_path = target_parsed.path.rstrip("/")
            actual_path = actual_parsed.path.rstrip("/")
            return not target_path or actual_path.startswith(target_path)
    except Exception:
        pass
    return target_value.casefold() in actual_value.casefold()


# -.-.-.-
def _state_changed(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    for key in ("url", "title", "active_tag", "active_id", "page_count"):
        if before.get(key) != after.get(key):
            return True
    return False


# -.-.-.-
def _element_state_changed(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    keys = ("checked", "expanded", "pressed", "selected", "value_length", "disabled")
    return any(before.get(key) != after.get(key) for key in keys)


# -.-.-.-
async def _page_snapshot(page) -> dict[str, Any]:
    title = ""
    scroll = [0, 0]
    active = {"tag": "", "id": ""}
    try:
        title = str(await page.title() or "")[:240]
    except Exception:
        pass
    try:
        value = await page.evaluate("() => [window.scrollX || 0, window.scrollY || 0]")
        if isinstance(value, (list, tuple)) and len(value) == 2:
            scroll = [int(value[0]), int(value[1])]
    except Exception:
        pass
    try:
        value = await page.evaluate(
            "() => ({tag: (document.activeElement?.tagName || '').toLowerCase(), id: document.activeElement?.id || ''})"
        )
        if isinstance(value, Mapping):
            active = {
                "tag": str(value.get("tag") or "")[:80],
                "id": str(value.get("id") or "")[:160],
            }
    except Exception:
        pass
    try:
        page_count = len(page.context.pages)
    except Exception:
        page_count = 0
    return {
        "url": str(getattr(page, "url", "") or "")[:1000],
        "title": title,
        "scroll": scroll,
        "active_tag": active["tag"],
        "active_id": active["id"],
        "page_count": int(page_count),
    }


# -.-.-.-
async def _element_state(locator) -> dict[str, Any]:
    try:
        element = locator.first
        if await element.count() <= 0:
            return {"exists": False}
        state = await element.evaluate(
            """el => ({
                checked: typeof el.checked === 'boolean' ? el.checked : null,
                expanded: el.getAttribute('aria-expanded'),
                pressed: el.getAttribute('aria-pressed'),
                selected: typeof el.selected === 'boolean' ? el.selected : el.getAttribute('aria-selected'),
                disabled: typeof el.disabled === 'boolean' ? el.disabled : el.getAttribute('aria-disabled'),
                valueLength: typeof el.value === 'string' ? el.value.length : null
            })"""
        )
        if not isinstance(state, Mapping):
            return {"exists": True}
        return {
            "exists": True,
            "checked": state.get("checked"),
            "expanded": state.get("expanded"),
            "pressed": state.get("pressed"),
            "selected": state.get("selected"),
            "disabled": state.get("disabled"),
            "value_length": state.get("valueLength"),
        }
    except Exception:
        return {"exists": False}


# -.-.-.-
async def _verify_navigation(session, target_url: str) -> str:
    from actions.browser_control import _normalize_url

    page = await session._get_page()
    target = _normalize_url(target_url)
    before = await _page_snapshot(page)
    delivered = False
    try:
        await page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        delivered = True
    except Exception:
        delivered = str(getattr(page, "url", "") or "") not in {"", "about:blank"}
    await asyncio.sleep(0.15)
    after = await _page_snapshot(page)
    verified = bool(delivered and _url_matches_target(after["url"], target))
    return _result(
        "go_to",
        ok=verified,
        delivered=delivered,
        verified=verified,
        message="Managed browser navigation verified." if verified else "Navigation was attempted, but the resulting URL did not verify the requested destination.",
        evidence={"before": before, "after": after, "target": target},
    )


# -.-.-.-
async def _verify_type(session, params: Mapping[str, Any], *, smart: bool = False) -> str:
    page = await session._get_page()
    text = str(params.get("text") or "")
    if not text:
        return _result("smart_type" if smart else "type", ok=False, delivered=False, verified=False, error="No text was provided.")

    description = str(params.get("description") or "")
    selector = str(params.get("selector") or "")
    locator = None
    method = "selector"
    if smart:
        candidates = [
            ("placeholder", page.get_by_placeholder(description, exact=False)),
            ("label", page.get_by_label(description, exact=False)),
            ("textbox", page.get_by_role("textbox", name=description)),
            ("searchbox", page.get_by_role("searchbox")),
            ("combobox", page.get_by_role("combobox", name=description)),
        ]
        for candidate_method, candidate in candidates:
            try:
                if await candidate.first.count() > 0:
                    method = candidate_method
                    locator = candidate.first
                    break
            except Exception:
                continue
    else:
        locator = page.locator(selector).first if selector else page.locator(":focus").first

    if locator is None:
        return _result("smart_type" if smart else "type", ok=False, delivered=False, verified=False, error="No matching input control was found.")

    clear_first = bool(params.get("clear_first", True))
    before = await _element_state(locator)
    delivered = False
    try:
        if clear_first:
            await locator.clear()
        await locator.type(text, delay=35)
        delivered = True
    except Exception as exc:
        return _result(
            "smart_type" if smart else "type",
            ok=False,
            delivered=delivered,
            verified=False,
            error=f"Browser text input failed: {exc}",
            evidence={"method": method, "before": before, "expected_length": len(text)},
        )

    actual = None
    try:
        actual = str(await locator.input_value())
    except Exception:
        pass
    after = await _element_state(locator)
    verified = bool(
        actual is not None
        and (
            actual == text
            if clear_first
            else actual.endswith(text) or text in actual
        )
    )
    return _result(
        "smart_type" if smart else "type",
        ok=verified,
        delivered=True,
        verified=verified,
        message="Browser input value verified." if verified else "Text was delivered, but the resulting input value could not be verified.",
        evidence={
            "method": method,
            "before": before,
            "after": after,
            "expected_length": len(text),
            "actual_length": len(actual) if isinstance(actual, str) else None,
        },
    )


# -.-.-.-
async def _verify_scroll(session, params: Mapping[str, Any]) -> str:
    page = await session._get_page()
    direction = str(params.get("direction") or "down").strip().lower()
    amount = max(1, min(abs(int(params.get("amount") or 500)), 5000))
    before = await _page_snapshot(page)
    delta = amount if direction == "down" else -amount
    try:
        await page.mouse.wheel(0, delta)
    except Exception as exc:
        return _result("scroll", ok=False, delivered=False, verified=False, error=f"Browser scroll failed: {exc}")
    await asyncio.sleep(0.12)
    after = await _page_snapshot(page)
    before_y = int(before.get("scroll", [0, 0])[1])
    after_y = int(after.get("scroll", [0, 0])[1])
    verified = after_y != before_y
    return _result(
        "scroll",
        ok=verified,
        delivered=True,
        verified=verified,
        message="Browser scroll position changed and was verified." if verified else "Scroll was delivered, but the page scroll position did not change.",
        evidence={"before": before, "after": after, "direction": direction, "amount": amount},
    )


# -.-.-.-
async def _resolve_click_locator(page, params: Mapping[str, Any], *, smart: bool):
    if smart:
        description = str(params.get("description") or "")
        for role in ("button", "link", "searchbox", "textbox", "menuitem", "tab"):
            try:
                candidate = page.get_by_role(role, name=description).first
                if await candidate.count() > 0:
                    return candidate, role
            except Exception:
                continue
        try:
            candidate = page.get_by_text(description, exact=False).first
            if await candidate.count() > 0:
                return candidate, "text"
        except Exception:
            pass
        return None, ""

    text = str(params.get("text") or "")
    selector = str(params.get("selector") or "")
    if text:
        return page.get_by_text(text, exact=False).first, "text"
    if selector:
        return page.locator(selector).first, "selector"
    return None, ""


# -.-.-.-
async def _verify_click(session, params: Mapping[str, Any], *, smart: bool = False) -> str:
    page = await session._get_page()
    locator, method = await _resolve_click_locator(page, params, smart=smart)
    action_name = "smart_click" if smart else "click"
    if locator is None:
        return _result(action_name, ok=False, delivered=False, verified=False, error="No matching browser element was found.")
    try:
        if await locator.count() <= 0:
            return _result(action_name, ok=False, delivered=False, verified=False, error="No matching browser element was found.")
    except Exception:
        pass

    page_before = await _page_snapshot(page)
    element_before = await _element_state(locator)
    try:
        await locator.click(timeout=8_000)
    except Exception as exc:
        return _result(action_name, ok=False, delivered=False, verified=False, error=f"Browser click failed: {exc}")
    await asyncio.sleep(0.18)
    page_after = await _page_snapshot(page)
    element_after = await _element_state(locator)
    observable = bool(_state_changed(page_before, page_after) or _element_state_changed(element_before, element_after))
    return _result(
        action_name,
        ok=observable,
        delivered=True,
        verified=observable,
        message="Browser click produced a verified observable state change." if observable else "The click was delivered, but no observable browser state change was verified.",
        evidence={
            "method": method,
            "before": page_before,
            "after": page_after,
            "element_before": element_before,
            "element_after": element_after,
        },
    )


# -.-.-.-
async def _verify_fill_form(session, params: Mapping[str, Any]) -> str:
    page = await session._get_page()
    fields = params.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return _result("fill_form", ok=False, delivered=False, verified=False, error="No form fields were provided.")

    verified_count = 0
    errors: list[str] = []
    evidence_fields: list[dict[str, Any]] = []
    for selector, value in fields.items():
        selector_text = str(selector)
        expected = str(value)
        try:
            locator = page.locator(selector_text).first
            await locator.fill(expected)
            actual = str(await locator.input_value())
            matched = actual == expected
            if matched:
                verified_count += 1
            evidence_fields.append(
                {
                    "selector": selector_text[:240],
                    "verified": matched,
                    "expected_length": len(expected),
                    "actual_length": len(actual),
                }
            )
        except Exception as exc:
            errors.append(f"{selector_text[:120]}: {type(exc).__name__}")
            evidence_fields.append({"selector": selector_text[:240], "verified": False})

    total = len(fields)
    verified = verified_count == total
    return _result(
        "fill_form",
        ok=verified,
        delivered=verified_count > 0,
        verified=verified,
        message="All managed-browser form fields were verified." if verified else "Some form fields could not be verified after input.",
        evidence={"field_count": total, "verified_count": verified_count, "fields": evidence_fields, "errors": errors[:10]},
    )


# -.-.-.-
async def _verify_new_tab(session, params: Mapping[str, Any]) -> str:
    page = await session._get_page()
    context = page.context
    before_count = len(context.pages)
    try:
        new_page = await context.new_page()
        session._page = new_page
    except Exception as exc:
        return _result("new_tab", ok=False, delivered=False, verified=False, error=f"Could not open managed browser tab: {exc}")
    after_count = len(context.pages)
    created = after_count == before_count + 1 and not new_page.is_closed()
    requested_url = str(params.get("url") or "").strip()
    navigation_verified = True
    final_url = str(new_page.url or "")
    if requested_url:
        from actions.browser_control import _normalize_url

        target = _normalize_url(requested_url)
        try:
            await new_page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            pass
        final_url = str(new_page.url or "")
        navigation_verified = _url_matches_target(final_url, target)
    verified = bool(created and navigation_verified)
    return _result(
        "new_tab",
        ok=verified,
        delivered=created,
        verified=verified,
        message="New managed browser tab verified." if verified else "A tab was created, but its requested navigation was not fully verified.",
        evidence={"before_page_count": before_count, "after_page_count": after_count, "url": final_url[:1000]},
    )


# -.-.-.-
async def _verify_close_tab(session) -> str:
    page = session._page
    if page is None or page.is_closed():
        return _result("close_tab", ok=False, delivered=False, verified=False, error="No active managed browser tab is open.")
    context = page.context
    before_count = len(context.pages)
    try:
        await page.close()
    except Exception as exc:
        return _result("close_tab", ok=False, delivered=False, verified=False, error=f"Could not close managed browser tab: {exc}")
    after_pages = context.pages
    after_count = len(after_pages)
    session._page = after_pages[-1] if after_pages else None
    verified = bool(page.is_closed() and after_count == max(0, before_count - 1))
    return _result(
        "close_tab",
        ok=verified,
        delivered=True,
        verified=verified,
        message="Managed browser tab closure verified." if verified else "Tab close was delivered, but the context page count did not verify closure.",
        evidence={"before_page_count": before_count, "after_page_count": after_count},
    )


# -.-.-.-
async def _verify_history(session, action: str) -> str:
    page = await session._get_page()
    before = await _page_snapshot(page)
    try:
        if action == "back":
            response = await page.go_back(timeout=10_000)
        else:
            response = await page.go_forward(timeout=10_000)
    except Exception as exc:
        return _result(action, ok=False, delivered=False, verified=False, error=f"Browser history action failed: {exc}")
    await asyncio.sleep(0.1)
    after = await _page_snapshot(page)
    verified = before.get("url") != after.get("url")
    return _result(
        action,
        ok=verified,
        delivered=response is not None or verified,
        verified=verified,
        message=f"Browser {action} navigation verified." if verified else f"Browser {action} was attempted, but the URL did not change.",
        evidence={"before": before, "after": after, "response_present": response is not None},
    )


# -.-.-.-
async def _verify_reload(session) -> str:
    page = await session._get_page()
    before = await _page_snapshot(page)
    try:
        response = await page.reload(wait_until="domcontentloaded", timeout=15_000)
    except Exception as exc:
        return _result("reload", ok=False, delivered=False, verified=False, error=f"Browser reload failed: {exc}")
    after = await _page_snapshot(page)
    verified = bool(not page.is_closed())
    return _result(
        "reload",
        ok=verified,
        delivered=True,
        verified=verified,
        message="Managed browser reload completed and the page remains active." if verified else "Reload returned but the page state could not be verified.",
        evidence={"before": before, "after": after, "response_status": getattr(response, "status", None)},
    )


# -.-.-.-
async def _dispatch(session, action: str, params: Mapping[str, Any]) -> str:
    if action == "go_to":
        return await _verify_navigation(session, str(params.get("url") or ""))
    if action == "search":
        from actions.browser_control import _SEARCH_ENGINES

        query = str(params.get("query") or "")
        engine = str(params.get("engine") or "google").lower()
        base = _SEARCH_ENGINES.get(engine, _SEARCH_ENGINES["google"])
        return await _verify_navigation(session, base + query.replace(" ", "+"))
    if action == "type":
        return await _verify_type(session, params)
    if action == "smart_type":
        return await _verify_type(session, params, smart=True)
    if action == "scroll":
        return await _verify_scroll(session, params)
    if action == "click":
        return await _verify_click(session, params)
    if action == "smart_click":
        return await _verify_click(session, params, smart=True)
    if action == "fill_form":
        return await _verify_fill_form(session, params)
    if action == "new_tab":
        return await _verify_new_tab(session, params)
    if action == "close_tab":
        return await _verify_close_tab(session)
    if action in {"back", "forward"}:
        return await _verify_history(session, action)
    if action == "reload":
        return await _verify_reload(session)
    return _result(action, ok=False, delivered=False, verified=False, error="Unsupported verified browser automation action.")


# -.-.-.-
def verified_browser_automation(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    browser = str(params.get("browser") or "").strip().lower() or None

    if action == "session_status":
        try:
            from actions.browser_control import _registry

            active = bool(_registry.has(browser))
            return _result(
                action,
                ok=True,
                delivered=True,
                verified=True,
                message="Managed browser session status read.",
                evidence={"browser": browser or "default", "active": active},
            )
        except Exception as exc:
            return _result(action, ok=False, delivered=False, verified=False, error=f"Could not read managed browser session status: {exc}")

    if not action:
        return _result("unknown", ok=False, delivered=False, verified=False, error="No browser action was specified.")

    try:
        from actions.browser_control import _registry

        session = _registry.get(browser)
        result = session.run(_dispatch(session, action, params), timeout=60)
        if player:
            try:
                player.write_log(f"SYS: Verified browser · {action}")
            except Exception:
                pass
        return result
    except concurrent.futures.TimeoutError:
        return _result(action, ok=False, delivered=False, verified=False, error="Verified browser action timed out after 60 seconds.")
    except Exception as exc:
        return _result(action, ok=False, delivered=False, verified=False, error=f"Verified browser action failed: {exc}")
