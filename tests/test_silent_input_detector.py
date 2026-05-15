"""Tests for SilentInputDetector — Bug A1.

Reproduces the user-facing failure mode where BlackHole is installed but
not routed (no Multi-Output Device set up in Audio MIDI Setup): the input
stream opens fine and silently delivers nothing. Today the user only finds
out at the end of the meeting when the transcript is empty and the meeting
gets marked 'error' with no explanation. The detector surfaces a warning
within seconds of recording start so the user can fix the routing while
the meeting is still in progress.
"""

import pytest

from src.silent_input_detector import SilentInputDetector


@pytest.fixture
def detector() -> SilentInputDetector:
    return SilentInputDetector(alert_after_seconds=10.0, silence_threshold=1e-5)


def test_no_alert_for_first_silent_sample(detector):
    """A single silent sample must not fire — that's just the first
    callback before the stream has warmed up."""
    assert detector.observe(system_rms=0.0, now=0.0) is False


def test_no_alert_before_threshold_elapses(detector):
    """Silence for less than the threshold window must not fire."""
    detector.observe(system_rms=0.0, now=0.0)
    assert detector.observe(system_rms=0.0, now=5.0) is False
    assert detector.observe(system_rms=0.0, now=9.5) is False


def test_alert_fires_after_threshold_elapses(detector):
    """Silence for >= alert_after_seconds must fire exactly once."""
    detector.observe(system_rms=0.0, now=0.0)
    assert detector.observe(system_rms=0.0, now=10.5) is True


def test_alert_fires_only_once_per_session(detector):
    """Once we've alerted, don't keep alerting — one warning is enough,
    spamming would flood the UI / WebSocket."""
    detector.observe(system_rms=0.0, now=0.0)
    assert detector.observe(system_rms=0.0, now=11.0) is True
    assert detector.observe(system_rms=0.0, now=20.0) is False
    assert detector.observe(system_rms=0.0, now=100.0) is False


def test_above_threshold_audio_resets_silence_timer(detector):
    """Real audio coming through must reset the silence clock so a brief
    quiet stretch later doesn't re-fire prematurely."""
    detector.observe(system_rms=0.0, now=0.0)
    detector.observe(system_rms=0.0, now=5.0)

    # Audio arrives — clock resets
    detector.observe(system_rms=0.5, now=6.0)

    # New silence stretch — only 4s in, must not fire yet
    detector.observe(system_rms=0.0, now=7.0)
    assert detector.observe(system_rms=0.0, now=15.0) is False

    # 11s of silence after the audio sample — now it can fire
    assert detector.observe(system_rms=0.0, now=18.0) is True


def test_reset_allows_a_fresh_alert(detector):
    """A new recording session (after reset) must be able to alert again."""
    detector.observe(system_rms=0.0, now=0.0)
    assert detector.observe(system_rms=0.0, now=11.0) is True

    detector.reset()

    detector.observe(system_rms=0.0, now=100.0)
    assert detector.observe(system_rms=0.0, now=111.0) is True


def test_threshold_is_inclusive_of_floor_noise(detector):
    """RMS values below the configured threshold count as silence; values
    just above count as audio. The 1e-5 default tolerates the noise floor
    of typical interfaces while still treating routed-but-quiet sources
    as audio."""
    # Slightly above threshold: counts as audio, no alert
    detector.observe(system_rms=2e-5, now=0.0)
    assert detector.observe(system_rms=2e-5, now=20.0) is False

    # Reset and try again at threshold boundary
    detector.reset()
    detector.observe(system_rms=0.0, now=0.0)
    assert detector.observe(system_rms=0.0, now=11.0) is True
