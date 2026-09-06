def test_owner_and_deadline_only_when_explicit():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"items": [
        {"text": "Enviar relatório até 15/09", "owner": "João", "confidence": 0.9},
        {"text": "Rever o PR", "confidence": 0.5},
    ]}})
    first, second = result["tasks"]
    assert first["owner"] == "João" and first["deadline"] == "15/09"
    assert second["owner"] is None and second["deadline"] is None
    assert second["confidence"] == 0.5
