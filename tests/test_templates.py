"""Tests for the summary template system."""

from pathlib import Path

from src.templates import SummaryTemplate, TemplateManager


def test_list_templates_returns_builtins(tmp_path: Path):
    """list_templates() returns at least the 5 built-in templates."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    templates = manager.list_templates()
    assert len(templates) >= 5


def test_get_template_standard(tmp_path: Path):
    """get_template('standard') returns a template with correct name."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    template = manager.get_template("standard")
    assert template is not None
    assert template.name == "standard"
    assert len(template.system_prompt) > 0


def test_get_template_nonexistent(tmp_path: Path):
    """get_template() returns None for a name that doesn't exist."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    assert manager.get_template("nonexistent") is None


def test_save_and_load_custom_template(tmp_path: Path):
    """A saved custom template appears in list and get."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    custom = SummaryTemplate(
        name="my-custom",
        description="A custom template for testing",
        system_prompt="You are a test summariser.",
        sections=["Section A", "Section B"],
    )
    manager.save_template(custom)

    # Verify via get_template.
    loaded = manager.get_template("my-custom")
    assert loaded is not None
    assert loaded.name == "my-custom"
    assert loaded.description == "A custom template for testing"
    assert loaded.system_prompt == "You are a test summariser."
    assert loaded.sections == ["Section A", "Section B"]

    # Verify it appears in list_templates.
    names = [t.name for t in manager.list_templates()]
    assert "my-custom" in names


def test_custom_overrides_builtin(tmp_path: Path):
    """A custom template named 'standard' overrides the built-in."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    override = SummaryTemplate(
        name="standard",
        description="My override",
        system_prompt="Custom standard prompt.",
        sections=["Only Section"],
    )
    manager.save_template(override)

    loaded = manager.get_template("standard")
    assert loaded is not None
    assert loaded.description == "My override"
    assert loaded.system_prompt == "Custom standard prompt."
    assert loaded.sections == ["Only Section"]


def test_delete_custom_template(tmp_path: Path):
    """Deleting a custom template removes it."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    custom = SummaryTemplate(
        name="to-delete",
        description="Will be deleted",
        system_prompt="Prompt.",
        sections=["S1"],
    )
    manager.save_template(custom)
    assert manager.get_template("to-delete") is not None

    result = manager.delete_template("to-delete")
    assert result is True
    assert manager.get_template("to-delete") is None


def test_delete_builtin_returns_false(tmp_path: Path):
    """Deleting a built-in template returns False (built-ins are in memory)."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    result = manager.delete_template("standard")
    assert result is False
    # The built-in should still be available.
    assert manager.get_template("standard") is not None


def test_delete_nonexistent_returns_false(tmp_path: Path):
    """Deleting a template that doesn't exist returns False."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    result = manager.delete_template("does-not-exist")
    assert result is False


def test_template_manager_creates_directory(tmp_path: Path):
    """Saving a template creates the templates directory if needed."""
    templates_dir = tmp_path / "deep" / "nested" / "templates"
    assert not templates_dir.exists()

    manager = TemplateManager(templates_dir=templates_dir)
    custom = SummaryTemplate(
        name="dir-test",
        description="Tests directory creation",
        system_prompt="Prompt.",
        sections=["S1"],
    )
    manager.save_template(custom)
    assert templates_dir.is_dir()


def test_builtin_templates_have_valid_sections(tmp_path: Path):
    """All built-in templates have a non-empty sections list."""
    manager = TemplateManager(templates_dir=tmp_path / "templates")
    builtins = manager.list_templates()
    builtin_names = {"standard", "standup", "retro", "1on1", "client-call"}
    for template in builtins:
        if template.name in builtin_names:
            assert len(template.sections) > 0, (
                f"Built-in template '{template.name}' has empty sections"
            )
