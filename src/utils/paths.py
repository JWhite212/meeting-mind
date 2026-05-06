"""
Centralised data paths for Context Recall.

All persistent data lives under macOS-native locations. This helper
exists so individual modules don't duplicate path construction.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Context Recall"


def app_support_dir() -> Path:
    return Path(os.path.expanduser(f"~/Library/Application Support/{APP_NAME}"))


def cache_dir() -> Path:
    return Path(os.path.expanduser(f"~/Library/Caches/{APP_NAME}"))


def logs_dir() -> Path:
    return Path(os.path.expanduser(f"~/Library/Logs/{APP_NAME}"))


def db_path() -> Path:
    return app_support_dir() / "meetings.db"


def audio_dir() -> Path:
    return app_support_dir() / "audio"


def auth_token_path() -> Path:
    return app_support_dir() / "auth_token"


def templates_dir() -> Path:
    return app_support_dir() / "templates"


def default_log_file() -> Path:
    return logs_dir() / "contextrecall.log"
