# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MeetingMind daemon.

Produces a directory-mode bundle at dist/meetingmind-daemon/ containing
the daemon binary and all dependencies. Directory mode is preferred over
one-file because:
  - Individual binaries can be codesigned on macOS
  - Faster startup (no temp extraction)
  - Easier debugging

Build: pyinstaller meetingmind.spec
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None

# Collect native libraries and data files for key dependencies.
datas = []
binaries = []

# faster-whisper: includes VAD model ONNX files.
datas += collect_data_files("faster_whisper")

# CTranslate2: native shared libraries.
binaries += collect_dynamic_libs("ctranslate2")
datas += collect_data_files("ctranslate2")

# MLX and MLX Whisper: Apple Silicon ML framework.
try:
    binaries += collect_dynamic_libs("mlx")
    datas += collect_data_files("mlx")
    datas += collect_data_files("mlx_whisper")
except Exception:
    pass  # Not available on non-Apple Silicon

# sounddevice: PortAudio shared library.
binaries += collect_dynamic_libs("sounddevice")
datas += collect_data_files("sounddevice")

# soundfile: libsndfile shared library.
binaries += collect_dynamic_libs("soundfile")
datas += collect_data_files("soundfile")

a = Analysis(
    ["src/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # Core pipeline
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "tokenizers",
        "numpy",
        "sounddevice",
        "soundfile",
        # MLX Whisper (Apple Silicon GPU transcription)
        "mlx",
        "mlx_whisper",
        # API server (uvicorn/starlette submodules collected below)
        "fastapi",
        "websockets",
        "aiosqlite",
        "pydantic",
        # Summarisation backends
        "anthropic",
        "httpx",
        # Output writers
        "notion_client",
        "slugify",
        "yaml",
        # Config and utilities
        "src",
        "src.main",
        "src.detector",
        "src.audio_capture",
        "src.transcriber",
        "src.diariser",
        "src.summariser",
        "src.platform",
        "src.platform.detector",
        "src.platform.macos",
        "src.api",
        "src.api.server",
        "src.api.events",
        "src.api.auth",
        "src.api.websocket",
        "src.api.routes",
        "src.api.routes.status",
        "src.api.routes.meetings",
        "src.api.routes.config",
        "src.api.routes.recording",
        "src.api.routes.devices",
        "src.api.routes.models",
        "src.api.routes.export",
        "src.api.routes.resummarise",
        "src.api.routes.reprocess",
        "src.api.routes.search",
        "src.api.routes.speakers",
        "src.api.routes.templates",
        "src.api.routes.analytics",
        "src.api.routes.calendar",
        "src.api.routes.notifications",
        "src.api.routes.prep",
        "src.api.routes.action_items",
        "src.api.routes.series",
        "src.api.schemas",
        "src.templates",
        "src.embeddings",
        "src.pyannote_diariser",
        "src.live_transcriber",
        "src.calendar_matcher",
        "src.scheduler",
        "src.db",
        "src.db.database",
        "src.db.repository",
        "src.output",
        "src.output.markdown_writer",
        "src.output.notion_writer",
        "src.action_items",
        "src.action_items.extractor",
        "src.action_items.repository",
        "src.analytics",
        "src.analytics.engine",
        "src.analytics.repository",
        "src.notifications",
        "src.notifications.channels",
        "src.notifications.channels.external",
        "src.notifications.channels.in_app",
        "src.notifications.channels.macos",
        "src.notifications.dispatcher",
        "src.notifications.repository",
        "src.prep",
        "src.prep.briefing",
        "src.prep.repository",
        "src.series",
        "src.series.detector",
        "src.series.repository",
        "src.utils",
        "src.utils.config",
        "src.utils.temporal",
    ]
    + collect_submodules("uvicorn")
    + collect_submodules("starlette")
    + collect_submodules("mlx")
    + collect_submodules("mlx_whisper"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not needed at runtime
        "tkinter",
        "matplotlib",
        "pytest",
        "ruff",
        "pip",
        "setuptools",
        # sentence-transformers and its heavy dependencies are optional
        # (semantic search degrades gracefully — see src/embeddings.py)
        # NOTE: scipy is kept — mlx_whisper.timing requires scipy.signal
        "torch",
        "torchvision",
        "torchaudio",
        "sentence_transformers",
        "transformers",
        "sklearn",
        "scikit-learn",
        # Other unused packages
        "PIL",
        "cv2",
        "IPython",
        "notebook",
        "sphinx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="meetingmind-daemon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name="meetingmind-daemon",
)
