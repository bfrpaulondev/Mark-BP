def test_preview_requires_confirmation():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"work": ["X"]}})
    assert result["requires_confirmation"] is True
    assert result["submitted"] is False
    assert "X" in result["report"]

def test_empty_data_is_not_invented():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {}})
    assert "(nenhum indicado)" in result["report"]
