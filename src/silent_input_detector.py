"""Detect a system-audio source that is open but silent.

Reproduces the user-facing symptom of Bug A1: BlackHole is installed (so
the input stream opens fine) but the user has not built a Multi-Output
Device in Audio MIDI Setup, so no system audio is actually routed to it.
The stream delivers a steady stream of zero samples and the user only
discovers the problem at the end of the meeting when the transcript is
empty.

The detector is a small state machine that the orchestrator feeds with
each audio.level callback. After ALERT_AFTER_SECONDS of continuous
sub-threshold input, observe() returns True exactly once per session;
the orchestrator turns that into a pipeline.warning event.

Time is injected so the detector is pure-function testable; production
callers pass time.monotonic().
"""

from __future__ import annotations


class SilentInputDetector:
    """One-shot silence detector for a single audio source."""

    def __init__(
        self,
        *,
        alert_after_seconds: float = 10.0,
        silence_threshold: float = 1e-5,
    ) -> None:
        self._alert_after_seconds = alert_after_seconds
        self._silence_threshold = silence_threshold
        self._silence_started_at: float | None = None
        self._alerted: bool = False

    def reset(self) -> None:
        """Clear state for a new recording session."""
        self._silence_started_at = None
        self._alerted = False

    def observe(self, *, system_rms: float, now: float) -> bool:
        """Record an audio level sample.

        Returns True iff this sample crosses the silence threshold for
        the first time in the current session. Subsequent calls return
        False even if silence persists, so the orchestrator only emits
        one warning per recording.
        """
        if self._alerted:
            return False

        if system_rms > self._silence_threshold:
            # Real audio — clear the silence clock.
            self._silence_started_at = None
            return False

        if self._silence_started_at is None:
            # First silent sample — start the clock.
            self._silence_started_at = now
            return False

        if now - self._silence_started_at >= self._alert_after_seconds:
            self._alerted = True
            return True

        return False
