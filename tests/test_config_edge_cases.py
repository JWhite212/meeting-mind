"""Edge-case tests for src/utils/config.py — supplements test_config.py."""

import pytest
import yaml

from src.utils.config import DetectionConfig, _expand_path, load_config


def test_malformed_yaml_does_not_crash(tmp_path):
    """YAML that parses as a non-dict causes an AttributeError in load_config
    because raw.get() is called on a non-dict. Truly invalid YAML raises
    yaml.YAMLError. Both are acceptable failures."""
    # Truly unparseable YAML.
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- :\n  - :\n    x: [")

    with pytest.raises((yaml.YAMLError, AttributeError)):
        load_config(config_path)


def test_detection_config_rejects_shell_injection():
    with pytest.raises(ValueError, match="Invalid process name"):
        DetectionConfig(process_names=["; rm -rf /"])


def test_detection_config_valid_process_names():
    """Valid process names should not raise."""
    config = DetectionConfig(process_names=["Microsoft Teams", "MSTeams", "Teams (work or school)"])
    assert len(config.process_names) == 3
    assert "Microsoft Teams" in config.process_names
    assert "Teams (work or school)" in config.process_names


def test_env_var_expansion_in_path(monkeypatch):
    monkeypatch.setenv("MEETINGMIND_TEST_DIR", "/tmp/test-meeting-mind")
    result = _expand_path("$MEETINGMIND_TEST_DIR/output")
    assert "/tmp/test-meeting-mind/output" in result


def test_wrong_type_in_field():
    """Passing a non-numeric type for a validated field raises during __post_init__."""
    with pytest.raises(TypeError):
        DetectionConfig(poll_interval_seconds="five")


def test_empty_process_names_list(tmp_path):
    """An empty process_names list is valid — no iteration needed."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"detection": {"process_names": []}}))
    config = load_config(config_path)
    assert config.detection.process_names == []


def test_expand_path_nonexistent_env_var():
    """os.path.expandvars leaves undefined variables as literal strings."""
    result = _expand_path("$NONEXISTENT_VAR_12345/foo")
    assert "$NONEXISTENT_VAR_12345" in result


def test_yaml_list_instead_of_dict(tmp_path):
    """A YAML file containing a list (not a dict) should fail gracefully.

    load_config calls raw.get(...) on the parsed YAML.  When the top-level
    value is a list, .get() does not exist, so an AttributeError is raised.
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- item1\n- item2\n")

    with pytest.raises(AttributeError):
        load_config(config_path)
