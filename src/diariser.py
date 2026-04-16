"""
Speaker diarisation with pluggable backends.

Provides a ``DiariserBackend`` Protocol for backends that operate on a
single combined audio file (e.g. pyannote) and a concrete
``EnergyDiariser`` that compares RMS energy between separate system and
microphone recordings.

Use :func:`create_diariser` to obtain the appropriate backend from a
:class:`DiarisationConfig`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import soundfile as sf

from src.transcriber import Transcript

logger = logging.getLogger(__name__)


@dataclass
class DiarisationConfig:
    enabled: bool = False
    speaker_name: str = "Me"  # Label for the local user.
    remote_label: str = "Remote"  # Label for remote participants.
    energy_ratio_threshold: float = 1.5  # How much louder one source must be.
    backend: str = "energy"  # "energy" or "pyannote"
    pyannote_model: str = "pyannote/speaker-diarization-3.1"
    num_speakers: int = 0  # 0 = auto-detect


@runtime_checkable
class DiariserBackend(Protocol):
    """Protocol for diarisation backends that use a single combined audio file."""

    def diarise(self, transcript: Transcript, audio_path: Path) -> Transcript:
        """Label each segment in *transcript* with a speaker identifier."""
        ...


class EnergyDiariser:
    """
    Labels transcript segments with speaker identifiers by comparing
    energy levels between mic and system audio recordings.
    """

    def __init__(self, config: DiarisationConfig):
        self._config = config

    def diarise(
        self,
        transcript: Transcript,
        system_audio_path: Path,
        mic_audio_path: Path,
    ) -> Transcript:
        """
        Label each segment in *transcript* with a speaker identifier.

        Compares RMS energy in the corresponding time window of each
        source file to determine who was speaking. Uses seek-based
        reading to avoid loading entire files into memory.

        Note:
            Mutates *transcript* in place. The same object is returned
            for method-chaining convenience.
        """
        for path, label in [
            (system_audio_path, "system audio"),
            (mic_audio_path, "mic audio"),
        ]:
            if not path.exists():
                raise FileNotFoundError(f"Diarisation requires {label} file: {path}")

        threshold = self._config.energy_ratio_threshold
        me = self._config.speaker_name
        remote = self._config.remote_label

        with (
            sf.SoundFile(str(system_audio_path)) as system_sf,
            sf.SoundFile(str(mic_audio_path)) as mic_sf,
        ):
            if system_sf.samplerate != mic_sf.samplerate:
                raise ValueError(
                    f"Sample rate mismatch: system={system_sf.samplerate}Hz, "
                    f"mic={mic_sf.samplerate}Hz"
                )

            sample_rate = system_sf.samplerate

            for segment in transcript.segments:
                start_sample = int(segment.start * sample_rate)
                end_sample = int(segment.end * sample_rate)
                num_frames = end_sample - start_sample

                if (
                    start_sample >= system_sf.frames
                    or start_sample >= mic_sf.frames
                    or num_frames <= 0
                ):
                    segment.speaker = ""
                    continue

                system_sf.seek(start_sample)
                sys_window = system_sf.read(frames=num_frames, dtype="float32")

                mic_sf.seek(start_sample)
                mic_window = mic_sf.read(frames=num_frames, dtype="float32")

                sys_rms = self._rms(sys_window)
                mic_rms = self._rms(mic_window)

                if mic_rms > sys_rms * threshold:
                    segment.speaker = me
                elif sys_rms > mic_rms * threshold:
                    segment.speaker = remote
                else:
                    segment.speaker = f"{me} + {remote}"

        # Log summary.
        counts: dict[str, int] = {}
        for seg in transcript.segments:
            counts[seg.speaker] = counts.get(seg.speaker, 0) + 1
        logger.info("Diarisation complete: %s", counts)

        return transcript

    @staticmethod
    def _rms(audio: np.ndarray) -> float:
        """Calculate RMS of an audio array."""
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio**2)))


def create_diariser(config: DiarisationConfig) -> DiariserBackend | EnergyDiariser:
    """
    Factory function that returns the appropriate diariser backend.

    Args:
        config: Diarisation configuration specifying which backend to use.

    Returns:
        An ``EnergyDiariser`` for the ``"energy"`` backend, or a
        ``DiariserBackend``-compatible object for other backends.

    Raises:
        ValueError: If the requested backend is unknown or its
            dependencies are not installed.
    """
    backend = config.backend

    if backend == "energy":
        return EnergyDiariser(config)

    if backend == "pyannote":
        try:
            import pyannote.audio  # noqa: F401
        except ImportError:
            raise ValueError(
                "Pyannote backend requires 'pyannote.audio' and its dependencies. "
                "Install with: pip install pyannote.audio"
            )
        raise ValueError("Pyannote backend is not yet implemented.")

    raise ValueError(
        f"Unknown diarisation backend: {backend!r}. Supported backends: 'energy', 'pyannote'."
    )
