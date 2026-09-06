def _skill():
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill

    return skill


def test_unauthorized_transcript_fails_closed():
    skill = _skill()
    result = skill.run({"args": {"segments": [{"text": "Decisão: lançar"}]}})
    assert result["ok"] is False
    assert result["error"] == "meeting_not_authorized"
    assert result["decisions"] == []


def test_extraction_and_speaker_uncertainty():
    skill = _skill()
    result = skill.run({"args": {"authorized": True, "segments": [
        {"speaker": None, "text": "Decisão: adiar o lançamento", "ts": 1},
        {"speaker": "João", "speaker_confirmed": False, "text": "Ação: enviar o relatório", "ts": 2},
        {"speaker": "Maria", "speaker_confirmed": True, "text": "Ação: rever o PR", "ts": 3},
        {"speaker": None, "text": "Estou bloqueado pela API", "ts": 4},
        {"speaker": None, "text": "Quem revê o PR?", "ts": 5},
    ]}})
    assert result["ok"] is True
    assert len(result["decisions"]) == 1
    assert "não confirmado" in result["decisions"][0]["speaker"]
    assert result["actions"][0]["speaker"] == "João? (não confirmado)"
    assert result["actions"][1]["speaker"] == "Maria"
    assert len(result["blockers"]) == 1
    assert len(result["questions"]) == 1
