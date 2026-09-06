def _speaker_label(speaker):
    return str(speaker) if speaker else "Speaker ? (não confirmado)"

def run(context):
    """Extracts decisions/actions/blockers/questions from authorized
    transcript segments using deterministic markers only."""
    segments = list((context.get("args") or {}).get("segments") or [])
    decisions, actions, blockers, questions = [], [], [], []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        low = text.lower()
        speaker = _speaker_label(seg.get("speaker"))
        entry = {"speaker": speaker, "text": text, "ts": seg.get("ts")}
        if low.startswith(("decisão:", "decidido", "decisão ")):
            decisions.append(entry)
        if low.startswith(("ação:", "acção:", "tarefa:")) or "fica responsável" in low:
            actions.append(entry)
        if "bloqueado" in low or low.startswith("bloqueio:"):
            blockers.append(entry)
        if "?" in text:
            questions.append(entry)
    return {"ok": True, "decisions": decisions, "actions": actions, "blockers": blockers, "questions": questions}
