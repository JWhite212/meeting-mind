"""
macOS meeting detection implementation.

Uses subprocess calls to pgrep, lsof, and osascript to detect active
meetings. These are inherently macOS-specific since BlackHole and the
rest of the audio pipeline are macOS-bound.
"""

import logging
import shutil
import subprocess

from src.platform.detector import DetectorError

logger = logging.getLogger(__name__)

# External binaries this detector depends on. Each must be present on
# PATH at construction time — a missing binary indicates a broken
# environment and must surface loudly rather than masquerade as
# "no meeting detected".
_REQUIRED_BINARIES = ("pgrep", "lsof", "osascript")


class MacOSDetector:
    """Detects meetings on macOS via process inspection and AppleScript."""

    def __init__(self) -> None:
        self._missing_binaries: tuple[str, ...] = tuple(
            name for name in _REQUIRED_BINARIES if shutil.which(name) is None
        )
        if self._missing_binaries:
            logger.error(
                "MacOSDetector cannot operate — missing required binaries on PATH: %s",
                ", ".join(self._missing_binaries),
            )

    def _require_binaries(self) -> None:
        """Raise ``DetectorError`` if any required binary is missing."""
        if self._missing_binaries:
            raise DetectorError(
                "Required binaries missing from PATH: " + ", ".join(self._missing_binaries)
            )

    def is_app_running(self, process_names: list[str]) -> bool:
        """Check if any of the given process names are currently running."""
        self._require_binaries()
        for name in process_names:
            try:
                result = subprocess.run(
                    ["pgrep", "-x", name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except subprocess.TimeoutExpired:
                logger.warning("pgrep timed out checking for %r", name)
                continue
            except FileNotFoundError:
                # PATH was valid at __init__ but pgrep disappeared — treat
                # as a hard error so it can't silently mask a meeting.
                raise DetectorError("pgrep disappeared from PATH at runtime") from None
        return False

    def is_app_using_audio(self, process_names: list[str]) -> bool:
        """
        Check if any of the given processes have active audio device handles.

        Looks for specific file descriptors that indicate active audio
        streaming, not just loaded libraries. Teams always loads CoreAudio
        libraries but only opens device handles during a call.
        """
        self._require_binaries()
        for name in process_names:
            try:
                pgrep = subprocess.run(
                    ["pgrep", "-x", name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if pgrep.returncode != 0:
                    continue

                pids = pgrep.stdout.strip().splitlines()
                for raw_pid in pids:
                    pid = raw_pid.strip()
                    if not pid or not pid.isdigit():
                        continue

                    lsof = subprocess.run(
                        ["lsof", "-p", pid],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    output = lsof.stdout.lower()

                    active_indicators = [
                        "ioaudioengine",
                        "appleusbaudio",
                        "blackhole",
                        "microsoftteamsaudio",
                    ]
                    if any(ind in output for ind in active_indicators):
                        return True

            except subprocess.TimeoutExpired:
                logger.warning("pgrep/lsof timed out for %r", name)
                continue
            except FileNotFoundError:
                raise DetectorError("pgrep or lsof disappeared from PATH at runtime") from None

        return False

    def is_call_window_active(self) -> bool:
        """
        Fallback heuristic: check if a Teams window title suggests an
        active call via AppleScript (requires Accessibility permissions).

        Uses pure-AppleScript case-insensitive comparison via an
        ``ignoring case`` block — no embedded ``do shell script`` /
        ``tr`` invocation, which previously interpolated window names
        into a shell command line.
        """
        self._require_binaries()
        script = (
            'tell application "System Events"\n'
            '    set teamsList to every process whose name contains "Teams"\n'
            "    repeat with teamsProc in teamsList\n"
            "        set winNames to name of every window of teamsProc\n"
            "        repeat with winName in winNames\n"
            "            set winText to (winName as text)\n"
            "            ignoring case\n"
            '                if winText contains "meeting"'
            ' or winText contains "call with"'
            ' or winText contains "in call" then\n'
            "                    return true\n"
            "                end if\n"
            "            end ignoring\n"
            "        end repeat\n"
            "    end repeat\n"
            "end tell\n"
            "return false"
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip().lower() == "true"
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            raise DetectorError("osascript disappeared from PATH at runtime") from None
