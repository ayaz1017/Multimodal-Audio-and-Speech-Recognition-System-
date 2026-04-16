"""
Audio utility functions — file saving, audio validation, and metadata extraction.
"""

from __future__ import annotations

import io
import struct
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.signal import butter, lfilter
import noisereduce as nr

from app.config import settings
from app.core.exceptions import AudioProcessingException


def save_audio_chunk(
    audio_data: bytes,
    session_id: str,
    chunk_index: int,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,  # 16-bit = 2 bytes
    suffix: str = "",
) -> Path:
    """
    Save a raw PCM audio chunk as a WAV file on disk.

    Args:
        audio_data: Raw PCM bytes (signed 16-bit little-endian).
        session_id: The session UUID string for directory organization.
        chunk_index: Sequential index of this chunk within the session.
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        sample_width: Bytes per sample (2 = 16-bit).
        suffix: Optional file name suffix (e.g. '_frag').
    """
    try:
        session_dir = settings.audio_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        filename = f"chunk_{chunk_index:06d}{suffix}.wav"
        filepath = session_dir / filename

        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)

        return filepath

    except Exception as e:
        raise AudioProcessingException(f"Failed to save audio chunk: {e}")


def merge_audio_chunks(session_id: str, sample_rate: int = 16000) -> Optional[Path]:
    """
    Concatenate all chunk WAV files for a session into a single WAV file.

    Returns:
        Path to the merged WAV file, or None if no chunks found.
    """
    session_dir = settings.audio_dir / session_id
    if not session_dir.exists():
        return None

    chunk_files = sorted(session_dir.glob("chunk_*.wav"))
    if not chunk_files:
        return None

    merged_path = session_dir / "full_session.wav"

    try:
        all_frames = b""
        params = None

        for chunk_path in chunk_files:
            with wave.open(str(chunk_path), "rb") as wf:
                if params is None:
                    params = wf.getparams()
                all_frames += wf.readframes(wf.getnframes())

        if params:
            with wave.open(str(merged_path), "wb") as out:
                out.setparams(params)
                out.writeframes(all_frames)

        return merged_path

    except Exception as e:
        raise AudioProcessingException(f"Failed to merge audio chunks: {e}")


def get_audio_duration(filepath: Path) -> float:
    """Get the duration of a WAV file in seconds."""
    try:
        with wave.open(str(filepath), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        return 0.0


def get_audio_file_info(filepath: Path) -> dict:
    """Extract metadata from a WAV file."""
    try:
        with wave.open(str(filepath), "rb") as wf:
            return {
                "duration_seconds": wf.getnframes() / float(wf.getframerate()),
                "sample_rate": wf.getframerate(),
                "channels": wf.getnchannels(),
                "sample_width": wf.getsampwidth(),
                "n_frames": wf.getnframes(),
                "size_bytes": filepath.stat().st_size,
            }
    except Exception:
        return {}


def pcm_bytes_to_numpy(
    pcm_data: bytes, 
    sample_rate: int = 16000,
    clean_signal: bool = True
) -> np.ndarray:
    """
    Convert raw PCM bytes (signed 16-bit little-endian) to a float32 numpy array.
    Values are normalized to the range [-1.0, 1.0].
    
    If clean_signal is True, applies HPF and AGC to improve ML accuracy.
    """
    try:
        n_samples = len(pcm_data) // 2
        samples = struct.unpack(f"<{n_samples}h", pcm_data)
        audio_array = np.array(samples, dtype=np.float32)
        audio_array = audio_array / 32768.0
        
        if clean_signal:
            # Apply production signal path
            audio_array = apply_highpass_filter(audio_array, sample_rate)
            audio_array = apply_spectral_gating(audio_array, sample_rate)
            audio_array = apply_agc(audio_array)
            
        return audio_array
    except Exception as e:
        raise AudioProcessingException(f"Failed to convert PCM to numpy: {e}")


def apply_highpass_filter(data: np.ndarray, sample_rate: int, cutoff: float = 100.0) -> np.ndarray:
    """Apply a Butterworth high-pass filter to remove low-frequency clinic rumble."""
    nyq = 0.5 * sample_rate
    normal_cutoff = cutoff / nyq
    b, a = butter(1, normal_cutoff, btype='high', analog=False)
    return lfilter(b, a, data).astype(np.float32)


def apply_spectral_gating(data: np.ndarray, sample_rate: int) -> np.ndarray:
    """
    Non-stationary spectral gating noise reduction.

    Surgically erases broadband environmental noise (AC hiss, laptop fans, room
    reverb, traffic) from each audio chunk BEFORE it enters the Wav2Vec2 model.
    Without this, the CNN maps acoustic noise directly to a 'Neutral/Calm' class,
    which is the primary driver of the 'random emotion' misclassification problem.

    Algorithm: Time-frequency masking using STFT, where a frequency-wise noise
    gate threshold is learned from the noisy audio itself (stationary=False allows
    adapting to changing noise across the chunk). prop_decrease=0.85 is calibrated
    to aggressively reduce noise while preserving speech formants.
    """
    if len(data) == 0:
        return data
    try:
        reduced = nr.reduce_noise(y=data, sr=sample_rate, stationary=False, prop_decrease=0.85)
        return reduced.astype(np.float32)
    except Exception:
        return data  # Graceful fallback: return original if noisereduce fails


def apply_preemphasis(data: np.ndarray, alpha: float = 0.97) -> np.ndarray:
    """Apply pre-emphasis filter to boost high frequencies (vital for formants/emotions)."""
    if len(data) == 0:
        return data
    em_data = np.append(data[0], data[1:] - alpha * data[:-1])
    return em_data.astype(np.float32)


def apply_agc(data: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Automatic Gain Control normalization. 
    Ensures consistent input volume regardless of patient distance from mic.
    """
    rms = np.sqrt(np.mean(data**2))
    if rms < 1e-6:
        return data
        
    current_db = 20 * np.log10(rms)
    gain = 10 ** ((target_db - current_db) / 20)
    
    # Apply gain and Clip to prevent digital distortion
    return np.clip(data * gain, -1.0, 1.0).astype(np.float32)


def compute_rms_energy(audio: np.ndarray) -> float:
    """Compute the root-mean-square energy of an audio signal."""
    return float(np.sqrt(np.mean(audio ** 2)))


def validate_audio_data(data: bytes, min_bytes: int = 1600) -> bool:
    """
    Basic validation of incoming audio data.

    Args:
        data: Raw audio bytes.
        min_bytes: Minimum expected size (50ms of 16kHz 16-bit mono = 1600 bytes).

    Returns:
        True if the data passes basic validation.
    """
    if not data or len(data) < min_bytes:
        return False
    # Check that byte count is even (16-bit samples)
    if len(data) % 2 != 0:
        return False
    return True
