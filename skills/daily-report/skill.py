def run(context):
    """Formats the daily report from user-provided data. Draft: preview only
    until explicitly confirmed; submission is out of scope for the skill."""
    args = context.get("args") or {}
    work = list(args.get("work") or [])
    meetings = list(args.get("meetings") or [])
    blockers = list(args.get("blockers") or [])
    lines = ["Relatório diário", "", "Trabalho realizado:"]
    lines += [f"- {item}" for item in work] or ["- (nenhum indicado)"]
    lines.append("Reuniões:")
    lines += [f"- {m}" for m in meetings] or ["- (nenhuma)"]
    lines.append("Bloqueios:")
    lines += [f"- {b}" for b in blockers] or ["- (nenhum)"]
    report = "\n".join(lines)
    confirmed = bool(args.get("confirmed"))
    return {
        "ok": True,
        "requires_confirmation": not confirmed,
        "report": report,
        "submitted": False,
    }
