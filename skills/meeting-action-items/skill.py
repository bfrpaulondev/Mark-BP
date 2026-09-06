import re

_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b")

def run(context):
    """Converts meeting items into structured tasks. Owner and deadline
    only when explicitly present — never inferred."""
    items = list((context.get("args") or {}).get("items") or [])
    tasks = []
    for item in items:
        text = str(item.get("text") or "").strip()
        owner = str(item.get("owner") or "").strip()
        deadline_match = _DATE_RE.search(text)
        tasks.append({
            "title": text,
            "owner": owner or None,
            "deadline": deadline_match.group(1) if deadline_match else None,
            "confidence": item.get("confidence", 0.5),
            "source_meeting": item.get("source_meeting"),
        })
    return {"ok": True, "tasks": tasks}
