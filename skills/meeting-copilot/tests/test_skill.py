def test_extraction_and_speaker_uncertainty():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"segments": [
        {"speaker": None, "text": "Decisão: adiar o lançamento", "ts": 1},
        {"speaker": "João", "text": "Ação: enviar o relatório", "ts": 2},
        {"speaker": None, "text": "Estou bloqueado pela API", "ts": 3},
        {"speaker": None, "text": "Quem revê o PR?", "ts": 4},
    ]}})
    assert len(result["decisions"]) == 1
    assert "não confirmado" in result["decisions"][0]["speaker"]
    assert result["actions"][0]["speaker"] == "João"
    assert len(result["blockers"]) == 1
    assert len(result["questions"]) == 1
