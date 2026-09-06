def run(context):
    """Aggregates the day's data into a short summary. Never invents entries."""
    args = context.get("args") or {}
    meetings = list(args.get("meetings") or [])
    tasks_done = list(args.get("tasks_done") or [])
    decisions = list(args.get("decisions") or [])
    blockers = list(args.get("blockers") or [])
    lines = [f"Reuniões: {len(meetings)}", f"Tarefas concluídas: {len(tasks_done)}",
             f"Decisões: {len(decisions)}", f"Bloqueios: {len(blockers)}"]
    if decisions:
        lines.append("Decisões do dia:")
        lines += [f"- {d}" for d in decisions]
    return {"ok": True, "summary": "\n".join(lines)}
