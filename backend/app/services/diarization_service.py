"""
Speaker diarization service using pyannote.audio.

Splits an audio chunk into segments belonging to different speakers
and maps them to semantic labels like 'doctor' and 'patient'.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# Handle missing dependencies gracefully if pyannote isn't installed
try:
    import torch
    from pyannote.audio import Pipeline
    from pyannote.core import Annotation
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """A segment of audio belonging to a single speaker."""
    start: float
    end: float
    speaker_id: str          # Raw ID from diarization (e.g., SPEAKER_00)
    speaker_label: str       # Mapped semantic label (e.g., doctor, patient)
    
    def to_dict(self) -> Dict[str, object]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker_id": self.speaker_id,
            "speaker_label": self.speaker_label,
        }


class DiarizationService:
    """
    Service for extracting speaker segments from audio chunks using
    pyannote.audio pretrained models.
    """

    def __init__(
        self, 
        sample_rate: int = 16000, 
        use_dummy_if_missing: bool = True
    ):
        """
        Initialize the diarization service.
        
        Args:
            sample_rate: Expected audio sample rate (Hz).
            use_dummy_if_missing: If True, falls back to a dummy implementation 
                                  when the actual model cannot be loaded.
        """
        self.sample_rate = sample_rate
        self.pipeline: Optional[Pipeline] = None
        self.is_dummy = False
        
        # Mapping from raw pyannote IDs (SPEAKER_00) to semantic roles (doctor/patient)
        self.speaker_mapping: Dict[str, str] = {}
        # Once we have identified both doctor and patient, we anchor the mapping
        self.is_anchored = False
        
        self._initialize_model(use_dummy_if_missing)

    def _initialize_model(self, use_dummy_if_missing: bool) -> None:
        """Load the pyannote pipeline using the HF token."""
        if not PYANNOTE_AVAILABLE:
            if use_dummy_if_missing:
                logger.warning("pyannote.audio not available. Using dummy diarization.")
                self.is_dummy = True
                return
            else:
                raise ImportError("pyannote.audio is required but not installed.")

        token = settings.HF_AUTH_TOKEN
        if not token or token == "your_huggingface_token_here":
            if use_dummy_if_missing:
                logger.warning("HF_AUTH_TOKEN missing or invalid. Using dummy diarization.")
                self.is_dummy = True
                return
            else:
                raise ValueError("HF_AUTH_TOKEN must be set in the environment.")

        start_time = time.perf_counter()
        logger.info("Loading pyannote/speaker-diarization-3.1 model...")
        
        try:
            # We use the full diarization pipeline, which handles segmentation and clustering
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token
            )
            
            # Use GPU if available (MPS on Mac, CUDA on Linux/Windows)
            if torch.cuda.is_available():
                self.pipeline.to(torch.device("cuda"))
                logger.info("Pyannote pipeline loaded on CUDA.")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.pipeline.to(torch.device("mps"))
                logger.info("Pyannote pipeline loaded on MPS (Apple Silicon).")
            else:
                logger.info("Pyannote pipeline loaded on CPU.")
                
            elapsed = time.perf_counter() - start_time
            logger.info("Pyannote model loaded successfully in %.2fs", elapsed)
            
        except Exception as e:
            logger.error("Failed to load pyannote pipeline: %s", e)
            if use_dummy_if_missing:
                logger.warning("Falling back to dummy diarization.")
                self.is_dummy = True
            else:
                raise

    def process_chunk(self, audio: np.ndarray, chunk_start_time: float = 0.0) -> List[SpeakerSegment]:
        """
        Process a chunk of audio and return speaker segments.
        
        For real-time chunked audio, pyannote might assign different generic IDs
        (SPEAKER_00) across chunks. We maintain a simple heuristic mapping
        within this service instance to keep the labels consistent ("doctor" / "patient").
        
        Args:
            audio: 1D float32 numpy array.
            chunk_start_time: Absolute offset of this chunk in the session (seconds).
            
        Returns:
            List of SpeakerSegment objects.
        """
        if self.is_dummy:
            return self._dummy_diarization(audio, chunk_start_time)
            
        # Ensure audio is 1D
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] > 1 else audio[0]
            
        # Pyannote expects tensor shape (channels, samples)
        tensor = torch.from_numpy(audio).unsqueeze(0)
        
        try:
            # Input format required by pyannote pipeline when passing tensors
            input_data = {"waveform": tensor, "sample_rate": self.sample_rate}
            
            # The pipeline returns an Annotation object
            # Optimization: inference_mode disables autograd for huge memory/speed savings
            # Optimization: constraint bounds drastically increase short-context clustering accuracy
            with torch.inference_mode():
                annotation: Annotation = self.pipeline(
                    input_data,
                    min_speakers=1,
                    max_speakers=2
                )
            
            segments = []
            # 'turn' is a pyannote Segment (start, end)
            # 'track' is a unique track identifier
            # 'speaker' is the clustered label (e.g. SPEAKER_00)
            for turn, track, speaker in annotation.itertracks(yield_label=True):
                # Map generic Pyannote ID to our semantic labels
                semantic_label = self._map_speaker(speaker)
                
                # Turn start/end are relative to the chunk. Add offset to get absolute time.
                segments.append(SpeakerSegment(
                    start=chunk_start_time + turn.start,
                    end=chunk_start_time + turn.end,
                    speaker_id=speaker,
                    speaker_label=semantic_label
                ))
            
            # If pyannote returned nothing (e.g., silence or too short), return a default segment
            if not segments:
                duration = len(audio) / self.sample_rate
                segments.append(SpeakerSegment(
                    start=chunk_start_time,
                    end=chunk_start_time + duration,
                    speaker_id="UNKNOWN",
                    speaker_label="unknown"
                ))
                
            return segments
            
        except Exception as e:
            logger.error("Diarization failed on chunk: %s", e)
            return self._dummy_diarization(audio, chunk_start_time)

    def _map_speaker(self, raw_speaker_id: str) -> str:
        """
        Map a raw Pyannote speaker ID to a semantic role (doctor or patient).
        Uses an 'anchoring' heuristic: the first speaker is the doctor,
        the second is the patient. Once both are found, the mapping is locked.
        """
        if raw_speaker_id in self.speaker_mapping:
            return self.speaker_mapping[raw_speaker_id]
            
        # If we are anchored, we don't allow new IDs to take primary roles
        # This handles cases where pyannote might jitter a new ID for the same person
        if self.is_anchored:
            logger.debug("Diarization anchored, mapping unknown ID %s to 'other'", raw_speaker_id)
            return "other"

        # Mapping heuristic
        if "doctor" not in self.speaker_mapping.values():
            self.speaker_mapping[raw_speaker_id] = "doctor"
            logger.info("Speaker %s anchored as DOCTOR", raw_speaker_id)
            return "doctor"
            
        if "patient" not in self.speaker_mapping.values():
            self.speaker_mapping[raw_speaker_id] = "patient"
            self.is_anchored = True # Both primary roles found
            logger.info("Speaker %s anchored as PATIENT. Diarization mapping LOCKED.", raw_speaker_id)
            return "patient"
            
        return "other"
        
    def _dummy_diarization(self, audio: np.ndarray, offset: float) -> List[SpeakerSegment]:
        """
        Provides a fake diarization result for development without a model.
        Alternates speakers based on timestamp to show UI transitions.
        """
        duration = len(audio) / self.sample_rate
        # Simple heuristic: swap roles every 10 seconds of session time
        cycle = int(offset / 10) % 2
        role = "doctor" if cycle == 0 else "patient"
        
        return [SpeakerSegment(
            start=offset,
            end=offset + duration,
            speaker_id=f"SPEAKER_DUMMY_{cycle}",
            speaker_label=role
        )]
        
    def reset(self) -> None:
        """Reset the speaker mapping. Call this when starting a new session."""
        self.speaker_mapping.clear()
        self.is_anchored = False
        logger.info("DiarizationService state reset")
