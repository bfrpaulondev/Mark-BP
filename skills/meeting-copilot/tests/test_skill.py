def test_unauthorized_fails_closed():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"segments": [{"text": "Decisão: X"}]}})
    assert result == {"ok": False, "error": "meeting_not_authorized"}

def test_authorized_extracts_with_speaker_confirmation():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"authorized": True, "segments": [
        {"speaker": "Maria", "text": "Decisão: adiar", "ts": 1},
        {"speaker": "João?", "text": "Ação: enviar", "ts": 2},
        {"speaker": None, "text": "bloqueado pela API", "ts": 3},
    ]}})
    assert result["ok"] is True and result["authorized"] is True
    assert result["decisions"][0]["speaker"] == "Maria"
    assert result["decisions"][0]["speaker_confirmed"] is True
    assert "não confirmado" in result["actions"][0]["speaker"]
    assert result["actions"][0]["speaker_confirmed"] is False
    assert len(result["blockers"]) == 1

def test_no_invention_without_markers():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"authorized": True, "segments": [{"text": "Bom dia"}]}})
    assert result["decisions"] == [] and result["actions"] == []
