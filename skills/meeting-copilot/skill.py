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
        "decisions": decisions,
        "actions": actions,
        "blockers": blockers,
        "questions": questions,
    }
