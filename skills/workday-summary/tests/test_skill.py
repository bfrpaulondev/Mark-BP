def test_summary_counts_and_never_invents():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import skill
    result = skill.run({"args": {"meetings": ["A"], "decisions": ["D1", "D2"]}})
    assert "Reuniões: 1" in result["summary"]
    assert "Tarefas concluídas: 0" in result["summary"]
    assert "- D1" in result["summary"] and "- D2" in result["summary"]
