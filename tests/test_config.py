"""Tests for config loading and dataclass construction."""

import os
from pathlib import Path

import yaml

from src.utils.config import (
    AppConfig,
    AudioConfig,
    DetectionConfig,
    TranscriptionConfig,
    _build_dataclass,
    _expand_path,
    load_config,
)


def test_load_valid_config(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump(
            {
                "detection": {"poll_interval_seconds": 5},
                "audio": {"mic_enabled": False},
                "transcription": {"model_size": "medium.en"},
            }
        )
    )
    config = load_config(config_file)
    assert config.detection.poll_interval_seconds == 5
    assert config.audio.mic_enabled is False
    assert config.transcription.model_size == "medium.en"


def test_load_missing_file_returns_defaults():
    config = load_config(Path("/nonexistent/config.yaml"))
    assert isinstance(config, AppConfig)
    assert config.detection.poll_interval_seconds == 3
    assert config.audio.mic_enabled is True
    assert config.transcription.model_size == "mlx-community/whisper-large-v3-turbo"


def test_unknown_keys_ignored():
    """_build_dataclass should silently skip keys not in the dataclass."""
    result = _build_dataclass(
        DetectionConfig,
        {
            "poll_interval_seconds": 10,
            "some_future_key": "value",
            "another_unknown": 42,
        },
    )
    assert result.poll_interval_seconds == 10
    assert not hasattr(result, "some_future_key")


def test_expand_path_tilde():
    expanded = _expand_path("~/Documents/test")
    assert "~" not in expanded
    assert expanded.startswith(os.path.expanduser("~"))


def test_expand_path_absolute():
    expanded = _expand_path("/absolute/path")
    assert expanded == "/absolute/path"


def test_dataclass_defaults_valid_types():
    """All default config values should be their expected types."""
    config = AppConfig()
    assert isinstance(config.detection, DetectionConfig)
    assert isinstance(config.audio, AudioConfig)
    assert isinstance(config.transcription, TranscriptionConfig)
    assert isinstance(config.detection.poll_interval_seconds, int)
    assert isinstance(config.audio.sample_rate, int)
    assert isinstance(config.audio.mic_enabled, bool)


def test_load_empty_yaml(tmp_path: Path):
    """An empty YAML file should produce default config."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    config = load_config(config_file)
    assert isinstance(config, AppConfig)
    assert config.detection.poll_interval_seconds == 3


def test_missing_file_still_expands_user_paths():
    """When the config file is missing, load_config early-returns AppConfig()
    with dataclass defaults. Those defaults contain literal '~' (e.g.
    log_file='~/Library/Logs/Context Recall/contextrecall.log') and the
    happy-path _expand_path() calls never run.

    Symptom in production (2026-05-15 install): the installed daemon's
    cwd was the .app bundle, so logging.FileHandler resolved
    '~/Library/...' relative to that cwd and wrote app logs to a literal
    '~' directory INSIDE the .app bundle — invisible to the user and
    deleted on every reinstall.

    Expansion of '~' in path defaults must happen regardless of whether
    a config file was loaded."""
    config = load_config(Path("/definitely/does/not/exist.yaml"))

    assert "~" not in config.logging.log_file, (
        f"log_file must have ~ expanded even when no config file is loaded; "
        f"got {config.logging.log_file!r}"
    )
    assert "~" not in config.audio.temp_audio_dir, (
        f"temp_audio_dir must have ~ expanded; got {config.audio.temp_audio_dir!r}"
    )
    assert "~" not in config.markdown.vault_path, (
        f"vault_path must have ~ expanded; got {config.markdown.vault_path!r}"
    )
    assert config.logging.log_file.startswith(os.path.expanduser("~")), (
        f"log_file should resolve into the user's home directory; got {config.logging.log_file!r}"
    )
