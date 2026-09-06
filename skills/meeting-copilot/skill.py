def _speaker_entry(speaker):
    """P2: separate identity from confirmation. A received string is
    never proven identity automatically — confirmed stays clean, an
    unverified guess is marked, and absent identity stays anonymous."""
    if speaker in (None, ""):
        return "Speaker ? (não confirmado)", False
    if speaker == str(speaker) and str(speaker).endswith("?"):
        return str(speaker) + " (não confirmado)", False
    return str(speaker), True


def run(context):
    """Extracts decisions/actions/blockers/questions from authorized
    transcript segments using deterministic markers only.

    P1: without explicit {"authorized": true} in the args the skill
    fails closed — no meeting is processed silently."""
    args = context.get("args") or {}
    if not args.get("authorized"):
        return {"ok": False, "error": "meeting_not_authorized"}

    segments = list(args.get("segments") or [])
    decisions, actions, blockers, questions = [], [], [], []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        low = text.lower()
        speaker, speaker_confirmed = _speaker_entry(seg.get("speaker"))
        entry = {
            "speaker": speaker,
            "speaker_confirmed": speaker_confirmed,
            "text": text,
            "ts": seg.get("ts"),
        }
        if low.startswith(("decisão:", "decidido", "decisão ")):
            decisions.append(entry)
        if low.startswith(("ação:", "acção:", "tarefa:")) or "fica responsável" in low:
            actions.append(entry)
        if "bloqueado" in low or low.startswith("bloqueio:"):
            blockers.append(entry)
        if "?" in text:
            questions.append(entry)
    return {
        "ok": True,
        "authorized": True,
        "decisions": decisions,
        "actions": actions,
        "blockers": blockers,
        "questions": questions,
    }
