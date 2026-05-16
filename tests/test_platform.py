"""Tests for the platform detection abstraction."""

import sys
from unittest.mock import patch

import pytest

from src.platform.detector import DetectorError, PlatformDetector, create_detector
from src.platform.linux import LinuxDetector
from src.platform.windows import WindowsDetector


def test_create_detector_returns_macos_on_darwin():
    if sys.platform != "darwin":
        pytest.skip("macOS-only test")
    from src.platform.macos import MacOSDetector

    detector = create_detector()
    assert isinstance(detector, MacOSDetector)


def test_macos_detector_implements_protocol():
    if sys.platform != "darwin":
        pytest.skip("macOS-only test")
    from src.platform.macos import MacOSDetector

    detector = MacOSDetector()
    assert isinstance(detector, PlatformDetector)


def test_macos_is_app_running_returns_bool():
    if sys.platform != "darwin":
        pytest.skip("macOS-only test")
    from src.platform.macos import MacOSDetector

    detector = MacOSDetector()
    result = detector.is_app_running(["nonexistent_process_xyz"])
    assert result is False


def test_linux_stub_raises():
    detector = LinuxDetector()
    with pytest.raises(NotImplementedError):
        detector.is_app_running(["test"])
    with pytest.raises(NotImplementedError):
        detector.is_app_using_audio(["test"])
    with pytest.raises(NotImplementedError):
        detector.is_call_window_active()


def test_windows_stub_raises():
    detector = WindowsDetector()
    with pytest.raises(NotImplementedError):
        detector.is_app_running(["test"])
    with pytest.raises(NotImplementedError):
        detector.is_app_using_audio(["test"])
    with pytest.raises(NotImplementedError):
        detector.is_call_window_active()


# ------------------------------------------------------------------
# MacOSDetector — missing-binary hardening
# ------------------------------------------------------------------


def _which_missing(name: str) -> str | None:
    """Helper: pretend every macOS-required binary is missing."""
    return None


def _which_only(*present: str):
    """Helper factory: a ``shutil.which`` substitute where only the
    listed binary names resolve."""

    def _which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in present else None

    return _which


class TestMacOSDetectorBinaryGuard:
    """``MacOSDetector`` must fail loud — not silently — when its
    external dependencies are missing from ``PATH``."""

    def test_is_app_running_raises_when_pgrep_missing(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform.macos import MacOSDetector

        with patch("src.platform.macos.shutil.which", side_effect=_which_only("lsof", "osascript")):
            detector = MacOSDetector()
        assert "pgrep" in detector._missing_binaries
        with pytest.raises(DetectorError):
            detector.is_app_running(["Teams"])

    def test_is_app_using_audio_raises_when_lsof_missing(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform.macos import MacOSDetector

        with patch(
            "src.platform.macos.shutil.which", side_effect=_which_only("pgrep", "osascript")
        ):
            detector = MacOSDetector()
        assert "lsof" in detector._missing_binaries
        with pytest.raises(DetectorError):
            detector.is_app_using_audio(["Teams"])

    def test_is_call_window_active_raises_when_osascript_missing(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform.macos import MacOSDetector

        with patch("src.platform.macos.shutil.which", side_effect=_which_only("pgrep", "lsof")):
            detector = MacOSDetector()
        assert "osascript" in detector._missing_binaries
        with pytest.raises(DetectorError):
            detector.is_call_window_active()

    def test_all_binaries_missing_lists_all_in_error(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform.macos import MacOSDetector

        with patch("src.platform.macos.shutil.which", side_effect=_which_missing):
            detector = MacOSDetector()
        assert set(detector._missing_binaries) == {"pgrep", "lsof", "osascript"}
        with pytest.raises(DetectorError) as exc:
            detector.is_app_running(["Teams"])
        message = str(exc.value)
        assert "pgrep" in message
        assert "lsof" in message
        assert "osascript" in message

    def test_no_raise_when_all_binaries_present(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform.macos import MacOSDetector

        # Real shutil.which on macOS finds all three.
        detector = MacOSDetector()
        assert detector._missing_binaries == ()
        # Calling is_app_running with a nonsense process must NOT raise.
        assert detector.is_app_running(["definitely_not_a_real_proc"]) is False


# ------------------------------------------------------------------
# MacOSDetector — AppleScript shell-injection surface removed
# ------------------------------------------------------------------


class TestMacOSDetectorAppleScriptHardening:
    """The fallback window-title check must do its case-insensitive
    comparison in pure AppleScript — no embedded ``do shell script``,
    no shell quoting of window names."""

    def test_call_window_script_has_no_shell_invocation(self):
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")
        from src.platform import macos as macos_module

        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

            class _R:
                stdout = "false"

            return _R()

        with patch.object(macos_module.subprocess, "run", side_effect=fake_run):
            detector = macos_module.MacOSDetector()
            detector.is_call_window_active()

        script = captured["cmd"][-1]
        # Pure AppleScript: no shell out, no quoted_form, no tr.
        assert "do shell script" not in script
        assert "quoted form" not in script
        assert "tr " not in script
        # Must use the case-insensitive AppleScript primitive instead.
        assert "ignoring case" in script
        assert "end ignoring" in script
