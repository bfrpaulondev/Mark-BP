<<<<<<< HEAD
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
=======
def _speaker_label(segment):
    speaker = str(segment.get("speaker") or "").strip()
    confirmed = segment.get("speaker_confirmed") is True
    if speaker and confirmed:
        return speaker
    if speaker:
        return f"{speaker}? (não confirmado)"
    return "Speaker ? (não confirmado)"


def run(context):
    """Extract deterministic meeting facts from explicitly authorized input.

    This draft never starts recording or obtains audio itself. A caller must
    explicitly mark the supplied transcript as authorized; otherwise the
    skill fails closed. Speaker names are treated as unconfirmed unless the
    upstream source explicitly marks them confirmed.
    """
    args = context.get("args") or {}
    if args.get("authorized") is not True:
        return {
            "ok": False,
            "error": "meeting_not_authorized",
            "decisions": [],
            "actions": [],
            "blockers": [],
            "questions": [],
        }

    raw_segments = args.get("segments") or []
    if not isinstance(raw_segments, (list, tuple)):
        return {
            "ok": False,
            "error": "segments_must_be_a_list",
            "decisions": [],
            "actions": [],
            "blockers": [],
            "questions": [],
        }

    decisions, actions, blockers, questions = [], [], [], []
    for segment in raw_segments:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        low = text.casefold()
        entry = {
            "speaker": _speaker_label(segment),
            "text": text,
            "ts": segment.get("ts"),
>>>>>>> origin/glm/skills-product-drafts
        }
        if low.startswith(("decisão:", "decidido", "decisão ")):
            decisions.append(entry)
        if low.startswith(("ação:", "acção:", "tarefa:")) or "fica responsável" in low:
            actions.append(entry)
        if "bloqueado" in low or low.startswith("bloqueio:"):
            blockers.append(entry)
        if "?" in text:
            questions.append(entry)
<<<<<<< HEAD
    return {
        "ok": True,
        "authorized": True,
=======

    return {
        "ok": True,
>>>>>>> origin/glm/skills-product-drafts
        "decisions": decisions,
        "actions": actions,
        "blockers": blockers,
        "questions": questions,
    }
