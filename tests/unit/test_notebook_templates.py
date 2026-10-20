

def test_every_notebook_loads_its_group_env_before_choosing_the_mode() -> None:
    """A generated workspace stores LAB_MODE in config/group.env; a notebook that only reads the environment runs the mock."""
    from pathlib import Path

    for source in sorted(Path("notebooks/authoring").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert "load_group_env(" in text, source.name
        assert text.index("load_group_env(") < text.index('os.getenv("LAB_MODE"'), source.name
