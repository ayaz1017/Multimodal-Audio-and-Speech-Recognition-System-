"""
Audio feature extraction using librosa.

Extracts MFCC, spectral, and prosodic features from raw audio numpy arrays
in real-time. All functions operate on pre-loaded numpy arrays to avoid
disk I/O in the hot path.

Performance notes:
  - A 3-second chunk at 16kHz = 48,000 samples
  - Full feature extraction takes ~15-40ms on modern hardware
  - All operations are vectorized via numpy/librosa (no Python loops)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# ── Default Configuration ────────────────────────────────────────
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_N_MFCC = 13
DEFAULT_N_FFT = 512         # ~32ms window at 16kHz (real-time friendly)
DEFAULT_HOP_LENGTH = 160    # 10ms hop → 100 frames/sec
DEFAULT_N_MELS = 40


@dataclass
class AudioFeatures:
    """
    Container for extracted audio features from a single chunk.

    All feature arrays are numpy arrays. Scalar summaries are provided
    for quick database storage, while full arrays are available for
    ML model input.
    """
    # ── MFCC Features ────────────────────────────────────────────
    mfcc: np.ndarray                      # Shape: (n_mfcc, n_frames)
    mfcc_delta: np.ndarray                # First derivative of MFCCs
    mfcc_delta2: np.ndarray               # Second derivative of MFCCs
    mfcc_mean: np.ndarray                 # Shape: (n_mfcc,) — per-coefficient mean
    mfcc_std: np.ndarray                  # Shape: (n_mfcc,) — per-coefficient std

    # ── Spectral Features ────────────────────────────────────────
    spectral_centroid: float              # "Brightness" of the sound
    spectral_bandwidth: float             # Width of the spectral band
    spectral_rolloff: float               # Frequency below which 85% energy
    zero_crossing_rate: float             # Rate of sign changes in signal

    # ── Prosodic / Energy Features ───────────────────────────────
    rms_energy: float                     # Root mean square energy
    rms_energy_std: float                 # Variation in energy over time
    pitch_mean: Optional[float] = None    # Fundamental frequency (F0) mean
    pitch_std: Optional[float] = None     # F0 variation (intonation)
    
    # ── Clinical Stability Markers ───────────────────────────────
    jitter: float = 0.0                   # Frequency instability (micro-tremors)
    shimmer: float = 0.0                  # Amplitude instability
    hf_content_ratio: float = 0.0         # High-frequency spectral energy ratio

    # ── Metadata ─────────────────────────────────────────────────
    duration_seconds: float = 0.0
    sample_rate: int = DEFAULT_SAMPLE_RATE
    n_frames: int = 0
    extraction_time_ms: float = 0.0       # Time taken to extract features

    def to_feature_vector(self) -> np.ndarray:
        """
        Flatten all features into a single 1D vector suitable for
        traditional ML models (SVM, XGBoost, etc.).

        Returns:
            np.ndarray of shape (feature_dim,) — typically ~40 features.
        """
        parts = [
            self.mfcc_mean,                            # 13
            self.mfcc_std,                             # 13
            np.array([
                self.spectral_centroid,                 # 1
                self.spectral_bandwidth,                # 1
                self.spectral_rolloff,                  # 1
                self.zero_crossing_rate,                # 1
                self.rms_energy,                        # 1
                self.rms_energy_std,                    # 1
                self.pitch_mean or 0.0,                 # 1
                self.pitch_std or 0.0,                  # 1
            ], dtype=np.float32),
        ]
        return np.concatenate(parts).astype(np.float32)

    def to_mel_spectrogram_input(self) -> np.ndarray:
        """
        Stack MFCC + deltas into a 2D array suitable for CNN/Transformer
        models that expect spectrogram-like input.

        Returns:
            np.ndarray of shape (3 * n_mfcc, n_frames) — e.g. (39, T)
        """
        return np.vstack([self.mfcc, self.mfcc_delta, self.mfcc_delta2])

    def to_dict(self) -> Dict[str, object]:
        """Serialize features to a JSON-safe dictionary."""
        return {
            "mfcc_mean": self.mfcc_mean.tolist(),
            "mfcc_std": self.mfcc_std.tolist(),
            "spectral_centroid": round(self.spectral_centroid, 4),
            "spectral_bandwidth": round(self.spectral_bandwidth, 4),
            "spectral_rolloff": round(self.spectral_rolloff, 4),
            "zero_crossing_rate": round(self.zero_crossing_rate, 6),
            "rms_energy": round(self.rms_energy, 6),
            "rms_energy_std": round(self.rms_energy_std, 6),
            "pitch_mean": round(self.pitch_mean, 2) if self.pitch_mean else None,
            "pitch_std": round(self.pitch_std, 2) if self.pitch_std else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "n_frames": self.n_frames,
            "feature_vector_dim": len(self.to_feature_vector()),
            "extraction_time_ms": round(self.extraction_time_ms, 2),
        }


class FeatureExtractor:
    """
    Real-time audio feature extractor using librosa.

    Designed for low-latency operation on short audio chunks (1-5 seconds).
    All parameters are set at construction time for consistent extraction
    across a session.

    Usage:
        extractor = FeatureExtractor(sample_rate=16000)
        features = extractor.extract(audio_numpy_array)
        vector = features.to_feature_vector()
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        n_mfcc: int = DEFAULT_N_MFCC,
        n_fft: int = DEFAULT_N_FFT,
        hop_length: int = DEFAULT_HOP_LENGTH,
        n_mels: int = DEFAULT_N_MELS,
        extract_pitch: bool = True,
    ):
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.extract_pitch = extract_pitch

        logger.info(
            "FeatureExtractor initialized: sr=%d, n_mfcc=%d, n_fft=%d, hop=%d",
            sample_rate, n_mfcc, n_fft, hop_length,
        )

    def extract(self, audio: np.ndarray) -> AudioFeatures:
        """
        Extract a comprehensive feature set from a raw audio array.

        Args:
            audio: 1D float32 numpy array, normalized to [-1.0, 1.0].
                   Expected shape: (n_samples,)

        Returns:
            AudioFeatures dataclass with all computed features.

        Raises:
            ValueError: If audio array is empty or wrong dtype.
        """
        start_time = time.perf_counter()

        # ── Input validation ─────────────────────────────────────
        if audio.size == 0:
            raise ValueError("Cannot extract features from empty audio array")

        audio = audio.astype(np.float32)

        # Ensure 1D
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] > 1 else audio[0]

        duration = len(audio) / self.sample_rate

        # ── MFCC extraction ──────────────────────────────────────
        mfcc = librosa.feature.mfcc(
            y=audio,
            sr=self.sample_rate,
            n_mfcc=self.n_mfcc,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            n_mels=self.n_mels,
        )

        # Delta (velocity) and delta-delta (acceleration)
        mfcc_delta = librosa.feature.delta(mfcc, order=1)
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2)

        # Summary statistics
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)

        n_frames = mfcc.shape[1]

        # ── Spectral features ────────────────────────────────────
        spectral_centroid = float(np.mean(
            librosa.feature.spectral_centroid(
                y=audio, sr=self.sample_rate,
                n_fft=self.n_fft, hop_length=self.hop_length,
            )
        ))

        spectral_bandwidth = float(np.mean(
            librosa.feature.spectral_bandwidth(
                y=audio, sr=self.sample_rate,
                n_fft=self.n_fft, hop_length=self.hop_length,
            )
        ))

        spectral_rolloff = float(np.mean(
            librosa.feature.spectral_rolloff(
                y=audio, sr=self.sample_rate,
                n_fft=self.n_fft, hop_length=self.hop_length,
            )
        ))

        zero_crossing_rate = float(np.mean(
            librosa.feature.zero_crossing_rate(
                y=audio, hop_length=self.hop_length,
            )
        ))

        # ── Energy features ──────────────────────────────────────
        rms = librosa.feature.rms(
            y=audio, frame_length=self.n_fft, hop_length=self.hop_length,
        )
        rms_energy = float(np.mean(rms))
        rms_energy_std = float(np.std(rms))

        # ── Pitch (F0) extraction ────────────────────────────────
        pitch_mean = None
        pitch_std = None
        jitter = 0.0

        if self.extract_pitch:
            try:
                f0, voiced_flag, _ = librosa.pyin(
                    audio,
                    fmin=librosa.note_to_hz("C2"),   # ~65 Hz
                    fmax=librosa.note_to_hz("C7"),   # ~2093 Hz
                    sr=self.sample_rate,
                    hop_length=self.hop_length,
                )
                # Filter out unvoiced frames (NaN values)
                voiced_f0 = f0[~np.isnan(f0)]
                if len(voiced_f0) > 0:
                    pitch_mean = float(np.mean(voiced_f0))
                    pitch_std = float(np.std(voiced_f0))
                    
                    # Heuristic Jitter: average absolute difference between consecutive F0 cycles
                    # normalized by the mean F0 (Local Jitter %)
                    if len(voiced_f0) > 1:
                        diffs = np.abs(np.diff(voiced_f0))
                        jitter = float(np.mean(diffs) / pitch_mean)
            except Exception as e:
                logger.debug("Pitch extraction failed (non-critical): %s", e)

        # ── Shimmer extraction ───────────────────────────────────
        # Heuristic Shimmer: average absolute difference between consecutive RMS magnitudes
        # normalized by the mean RMS (Local Shimmer %)
        shimmer = 0.0
        if len(rms[0]) > 1:
            rms_vals = rms[0]
            shimmer = float(np.mean(np.abs(np.diff(rms_vals))) / (np.mean(rms_vals) + 1e-9))

        # ── High-Frequency Content Ratio ─────────────────────────
        # Ratio of spectral centroid to bandwidth - helps identify "shrill" vs "warm" tones
        hf_content_ratio = spectral_centroid / (spectral_bandwidth + 1e-9)

        # ── Timing ───────────────────────────────────────────────
        extraction_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "Features extracted: %d frames, %.1fms (%.1fs audio)",
            n_frames, extraction_time_ms, duration,
        )

        return AudioFeatures(
            mfcc=mfcc,
            mfcc_delta=mfcc_delta,
            mfcc_delta2=mfcc_delta2,
            mfcc_mean=mfcc_mean,
            mfcc_std=mfcc_std,
            spectral_centroid=spectral_centroid,
            spectral_bandwidth=spectral_bandwidth,
            spectral_rolloff=spectral_rolloff,
            zero_crossing_rate=zero_crossing_rate,
            rms_energy=rms_energy,
            rms_energy_std=rms_energy_std,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            jitter=jitter,
            shimmer=shimmer,
            hf_content_ratio=hf_content_ratio,
            duration_seconds=duration,
            sample_rate=self.sample_rate,
            n_frames=n_frames,
            extraction_time_ms=extraction_time_ms,
        )

    def extract_mfcc_only(self, audio: np.ndarray) -> np.ndarray:
        """
        Fast path: extract only MFCCs without spectral/prosodic features.
        Use this when you need maximum throughput and only need MFCC input
        for a neural network.

        Args:
            audio: 1D float32 numpy array.

        Returns:
            MFCC array of shape (n_mfcc, n_frames).
        """
        audio = audio.astype(np.float32)
        return librosa.feature.mfcc(
            y=audio,
            sr=self.sample_rate,
            n_mfcc=self.n_mfcc,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            n_mels=self.n_mels,
        )
