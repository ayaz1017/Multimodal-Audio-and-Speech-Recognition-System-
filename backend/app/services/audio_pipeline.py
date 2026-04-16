"""
Real-time audio processing pipeline.

Orchestrates the full processing flow for each audio chunk:
  PCM bytes → numpy → feature extraction → ML inference → result

Designed as a stateful pipeline that maintains a rolling window of
recent results for computing session-level aggregates like depression
score trends and emotion volatility.

Performance budget per chunk (3s audio):
  - PCM → numpy:         ~1ms
  - Feature extraction:   ~15-40ms
  - ML inference:         ~5-50ms (placeholder ~1ms, real model ~50ms)
  - Depression scoring:   ~1ms
  - Total target:         < 100ms
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple, Union

import numpy as np

from app.services.audio_utils import compute_rms_energy, pcm_bytes_to_numpy
from app.services.diarization_service import DiarizationService, SpeakerSegment
from app.services.feature_extractor import AudioFeatures, FeatureExtractor
from app.services.hybrid_emotion import HybridEmotionEngine
from app.services.inference_bridge import (
    DepressionIndicators,
    EmotionPrediction,
    InferenceModel,
    PlaceholderEmotionModel,
    Wav2Vec2EmotionModel,
)

logger = logging.getLogger(__name__)

# ── Depression Score Weights ─────────────────────────────────────
DEPRESSION_WEIGHTS = {
    "emotion_valence_ratio": 0.35,
    "energy_level": 0.15,
    "pitch_variability": 0.15,
    "speaking_rate_factor": 0.15,
    "emotion_volatility": 0.20,
}

NEGATIVE_EMOTIONS = {"sad", "fearful", "fear", "angry", "anger", "disgust", "surprised", "surprise"}
POSITIVE_EMOTIONS = {"happy", "calm", "neutral"}

# Maximum number of recent results to keep in the rolling window
ROLLING_WINDOW_SIZE = 60  # ~60 chunks × 3s = ~3 minutes of history


@dataclass
class PipelineResult:
    """
    Complete result from processing a single audio chunk.
    Contains features, emotion prediction, depression indicators, and timing.
    """
    chunk_index: int
    duration_seconds: float
    speaker: str                              # Dominant speaker label (e.g. "doctor")
    diarization_segments: List[SpeakerSegment] # Full list of diarization segments for this chunk
    features: AudioFeatures
    emotion: EmotionPrediction
    depression_score: float                   # 0-100 composite score
    depression_category: str                  # Normal, Mild, Moderate, Severe
    depression_indicators: DepressionIndicators
    rms_energy: float
    total_processing_time_ms: float

    # Session-level rolling aggregates
    rolling_depression_avg: float             # Average over recent window
    depression_trend: str                     # "increasing" | "decreasing" | "stable"
    dominant_session_emotion: str             # Most frequent emotion so far
    transcript: str = ""                      # Whisper ASR transcript for this chunk

    def to_dict(self) -> Dict[str, object]:
        """Serialize the full result to a JSON-safe dictionary."""
        return {
            "chunk_index": self.chunk_index,
            "duration_seconds": round(self.duration_seconds, 3),
            "speaker": self.speaker,
            "diarization_segments": [s.to_dict() for s in self.diarization_segments],
            "emotion": self.emotion.to_dict(),
            "depression_score": round(self.depression_score, 2),
            "depression_category": self.depression_category,
            "depression_indicators": self.depression_indicators.to_dict(),
            "depression_trend": self.depression_trend,
            "rolling_depression_avg": round(self.rolling_depression_avg, 2),
            "dominant_session_emotion": self.dominant_session_emotion,
            "rms_energy": round(self.rms_energy, 6),
            "features_summary": {
                "mfcc_mean": self.features.mfcc_mean.tolist(),
                "spectral_centroid": round(self.features.spectral_centroid, 2),
                "spectral_bandwidth": round(self.features.spectral_bandwidth, 2),
                "pitch_mean": (
                    round(self.features.pitch_mean, 2)
                    if self.features.pitch_mean else None
                ),
            },
            "timing": {
                "feature_extraction_ms": round(self.features.extraction_time_ms, 2),
                "inference_ms": round(self.emotion.inference_time_ms, 2),
                "total_ms": round(self.total_processing_time_ms, 2),
            },
            "transcript": self.transcript,
            "live_metrics": {
                "energy": min(100, round((self.features.rms_energy / 0.15) * 100, 1)),
                "pitch": min(100, round(((self.features.pitch_mean or 150) / 300) * 100, 1)),
                "tone": min(100, round((self.features.spectral_centroid / 3000) * 100, 1)),
            }
        }


class AudioPipeline:
    """
    Stateful real-time audio processing pipeline.

    Maintains session context (rolling history) and orchestrates:
      1. PCM → numpy conversion
      2. Feature extraction (MFCC, spectral, prosodic)
      3. ML emotion inference
      4. Depression score calculation

    Usage:
        pipeline = AudioPipeline()
        for chunk_bytes in audio_stream:
            result = pipeline.process_chunk(chunk_bytes, chunk_index)
            send_to_client(result.to_dict())
        summary = pipeline.get_session_summary()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        model: Optional[InferenceModel] = None,
        extract_pitch: bool = True,
    ):
        """
        Initialize the pipeline using pre-loaded singleton models.
        """
        from app.core.models import model_manager
        
        self.sample_rate = sample_rate
        self.extractor = FeatureExtractor(
            sample_rate=sample_rate,
            extract_pitch=extract_pitch,
        )
        self.model = model or model_manager.get_emotion_model()
        self.diarizer = model_manager.get_diarizer()
        self.hybrid = model_manager.get_hybrid_engine()

        # ── Rolling state ────────────────────────────────────────
        self._depression_scores: Deque[float] = deque(maxlen=ROLLING_WINDOW_SIZE)
        self._emotion_history: Deque[str] = deque(maxlen=ROLLING_WINDOW_SIZE)
        self._confidence_history: Deque[float] = deque(maxlen=ROLLING_WINDOW_SIZE)
        self._energy_history: Deque[float] = deque(maxlen=ROLLING_WINDOW_SIZE)
        self._chunks_processed: int = 0
        
        # Decision Smoothing — balanced hysteresis for clinical stability
        self._emotion_probs_ema: Optional[Dict[str, float]] = None
        self._smoothing_alpha = 0.6    # New frame = 40% weight, history = 60% (responds in ~7s)
        self._entropy_threshold = 1.8  # Reject high-uncertainty frames (8 classes max = 2.08 bits)
        self._silence_frames = 0       # Track consecutive silent frames

        logger.info(
            "AudioPipeline initialized: sr=%d, model=%s, pitch=%s",
            sample_rate, type(self.model).__name__, extract_pitch,
        )
        # Ensure clean slate (reset diarizer and buffers)
        self.reset()

    def process_chunk(
        self,
        pcm_data: Union[bytes, np.ndarray],
        chunk_index: int,
        force_patient: bool = False,
    ) -> PipelineResult:
        """
        Process a single audio chunk through the full pipeline.
        Accepts either raw PCM bytes (live mic) or pre-loaded np.ndarray (offline file).
        """
        pipeline_start = time.perf_counter()
        
        # Silence threshold — lower to capture quiet emotional speech
        # (sad, fear, disgust tend to be spoken softly)
        SILENCE_THRESHOLD = 0.002

        # ── Step 1: PCM → numpy ──────────────────────────────────
        if isinstance(pcm_data, np.ndarray):
            audio_np = pcm_data.astype(np.float32)
            # Note: offline numpy array should already have gating/AGC applied,
            # or we apply it here if needed. We assume it's pre-processed or we process it.
        else:
            audio_np = pcm_bytes_to_numpy(pcm_data, self.sample_rate)
            
        duration = len(audio_np) / self.sample_rate
        rms = compute_rms_energy(audio_np)

        # ── Step 2: Diarization ──────────────────────────────────
        chunk_start_time = chunk_index * duration
        segments = self.diarizer.process_chunk(audio_np, chunk_start_time)
        
        # Determine dominant speaker
        if force_patient:
            dominant_speaker = "patient"
        elif segments:
            dominant_speaker = max(segments, key=lambda s: s.end - s.start).speaker_label
        else:
            dominant_speaker = "unknown"

        # ── Step 3: Feature extraction ───────────────────────────
        features = self.extractor.extract(audio_np)

        # ── Step 4: ML inference ─────────────────────────────────
        feature_vector = features.to_feature_vector()
        
        if dominant_speaker == "patient" and rms > SILENCE_THRESHOLD:
            # ── Step 4a: Acoustic emotion (Wav2Vec2) ─────────────────
            acoustic_pred = self.model.predict_emotion(
                audio=audio_np,
                features=feature_vector,
            )
            self._silence_frames = 0

            # ── Step 4b: Hybrid Fusion (ASR + Text Emotion) ──────────
            # Transcribe the chunk with Whisper, classify via DistilRoBERTa,
            # then fuse acoustic + linguistic distributions for higher accuracy.
            transcript = ""
            if self.hybrid and self.hybrid.is_ready:
                try:
                    transcript = self.hybrid.transcribe(audio_np)
                    text_dist  = self.hybrid.text_emotion_distribution(transcript)
                    fused_dist = self.hybrid.fuse(
                        acoustic_distribution=acoustic_pred.distribution,
                        text_distribution=text_dist,
                        transcript=transcript,
                    )
                    # Rebuild the prediction with the fused distribution
                    fused_label = max(fused_dist, key=fused_dist.get)
                    raw_emotion = EmotionPrediction(
                        label=fused_label,
                        confidence=fused_dist[fused_label],
                        distribution=fused_dist,
                        entropy=acoustic_pred.entropy,
                        inference_time_ms=acoustic_pred.inference_time_ms,
                    )
                except Exception as ex:
                    logger.warning("Hybrid fusion failed, using acoustic only: %s", ex)
                    raw_emotion = acoustic_pred
            else:
                raw_emotion = acoustic_pred

            # ── Step 4c: PROSODIC FLATNESS LOCK (The "Ultra" Override) ──
            # Heuristic: If pitch variability and energy variability are both 
            # extremely low, this is a diagnostic marker for 'flat affect'.
            # We force a clinical bias towards neutral/sad.
            flat_affect_detected = False
            if features.pitch_std is not None and features.pitch_mean is not None:
                # pitch_var < 0.05 is extremely monotone
                if features.pitch_std / features.pitch_mean < 0.05 and features.rms_energy_std < 0.005:
                    flat_affect_detected = True

            if flat_affect_detected:
                # Scale up clinical indicators and scale down 'happy/surprise'
                raw_emotion.distribution["sad"]     *= 1.5
                raw_emotion.distribution["neutral"] *= 1.5
                raw_emotion.distribution["happy"]   *= 0.1
                raw_emotion.distribution["surprise"] *= 0.1
                
                # Re-normalize
                t = sum(raw_emotion.distribution.values())
                raw_emotion.distribution = {k: v/t for k, v in raw_emotion.distribution.items()}
                raw_emotion.label = max(raw_emotion.distribution, key=raw_emotion.distribution.get)

            # ── Entropy Gate: skip extremely uncertain frames ─────
            # If entropy is very high, the model is confused — hold last state
            if raw_emotion.entropy > self._entropy_threshold and self._emotion_probs_ema:
                emotion = EmotionPrediction(
                    label=max(self._emotion_probs_ema, key=self._emotion_probs_ema.get),
                    confidence=max(self._emotion_probs_ema.values()),
                    distribution=self._emotion_probs_ema.copy(),
                    entropy=raw_emotion.entropy,
                    inference_time_ms=raw_emotion.inference_time_ms,
                )

            # ── Confidence Gate: Reject frames where model is insufficiently sure ─
            # A flat distribution across 8 classes gives ~12.5% per class.
            # Threshold at 30% means the model has real signal, not noise-induced guessing.
            elif raw_emotion.confidence < 0.30 and self._emotion_probs_ema:
                emotion = EmotionPrediction(
                    label=max(self._emotion_probs_ema, key=self._emotion_probs_ema.get),
                    confidence=max(self._emotion_probs_ema.values()),
                    distribution=self._emotion_probs_ema.copy(),
                    entropy=raw_emotion.entropy,
                    inference_time_ms=raw_emotion.inference_time_ms,
                )
            else:
                # ── Heavy EMA: Historical context dominates (alpha=0.85) ─
                # alpha=0.85 means: result = 15% raw + 85% history
                # This cures "random jumping" by requiring a sustained emotional state to shift
                if self._emotion_probs_ema is None:
                    self._emotion_probs_ema = raw_emotion.distribution.copy()
                else:
                    for label, prob in raw_emotion.distribution.items():
                        prev = self._emotion_probs_ema.get(label, 0.0)
                        self._emotion_probs_ema[label] = (
                            (1 - self._smoothing_alpha) * prob +
                            self._smoothing_alpha * prev
                        )

                display_label = max(self._emotion_probs_ema, key=self._emotion_probs_ema.get)
                emotion = EmotionPrediction(
                    label=display_label,
                    confidence=self._emotion_probs_ema.get(display_label, 0.0),
                    distribution=self._emotion_probs_ema.copy(),
                    entropy=raw_emotion.entropy,
                    inference_time_ms=raw_emotion.inference_time_ms,
                )
        else:
            self._silence_frames += 1

            # Reset EMA after 3 consecutive silent frames so old emotion
            # doesn't bleed into next speech segment
            if self._silence_frames >= 3:
                self._emotion_probs_ema = None

            if self._emotion_probs_ema:
                # Decay confidence slightly during silence
                decay_factor = 0.95
                for label in self._emotion_probs_ema:
                    self._emotion_probs_ema[label] *= decay_factor
                
                # Re-normalize to ensure it remains a probability distribution
                total = sum(self._emotion_probs_ema.values())
                if total > 0:
                    for label in self._emotion_probs_ema:
                        self._emotion_probs_ema[label] /= total
                
                smoothed_label = max(self._emotion_probs_ema, key=self._emotion_probs_ema.get)
                emotion = EmotionPrediction(
                    label=smoothed_label,
                    confidence=self._emotion_probs_ema[smoothed_label],
                    distribution=self._emotion_probs_ema.copy(),
                    inference_time_ms=0.0
                )
            else:
                # Default fallback if no state exists yet
                emotion = EmotionPrediction(
                    label="calm",
                    confidence=1.0,
                    distribution={
                        "calm": 1.0, "happy": 0.0, "sad": 0.0, 
                        "anger": 0.0, "fear": 0.0, "disgust": 0.0
                    },
                    inference_time_ms=0.0
                )

        # ── Step 5: Update rolling state (for frequency) ─────────
        self._emotion_history.append(emotion.label)

        # ── Step 6: Depression scoring & categorization ──────────
        # Calculate real-time negative frequency based purely on emotions
        # (lightweight logic)
        neg_count = sum(1 for e in self._emotion_history if e in NEGATIVE_EMOTIONS)
        frequency = neg_count / len(self._emotion_history) if self._emotion_history else 0.0
        depression_score = frequency * 100.0
        depression_category = self._categorize_depression(depression_score)

        # Keep legacy indicators for compatibility, but score is overridden
        indicators = self._compute_depression_indicators(features, emotion)

        self._depression_scores.append(depression_score)
        self._confidence_history.append(emotion.confidence)
        self._energy_history.append(rms)
        self._chunks_processed += 1

        # ── Step 7: Compute aggregates ───────────────────────────
        rolling_avg = (
            sum(self._depression_scores) / len(self._depression_scores)
        )
        trend = self._compute_trend()
        dominant = self._compute_dominant_emotion()

        total_ms = (time.perf_counter() - pipeline_start) * 1000

        logger.debug(
            "Chunk %d processed: emotion=%s (%.2f), depression=%.1f, "
            "total=%.1fms",
            chunk_index, emotion.label, emotion.confidence,
            depression_score, total_ms,
        )

        return PipelineResult(
            chunk_index=chunk_index,
            duration_seconds=duration,
            speaker=dominant_speaker,
            diarization_segments=segments,
            features=features,
            emotion=emotion,
            depression_score=depression_score,
            depression_category=depression_category,
            depression_indicators=indicators,
            rms_energy=rms,
            total_processing_time_ms=total_ms,
            rolling_depression_avg=rolling_avg,
            depression_trend=trend,
            dominant_session_emotion=dominant,
            transcript=transcript if dominant_speaker == "patient" and rms > 0.002 else "",
        )

    # ── Depression Scoring ───────────────────────────────────────
    def _compute_depression_indicators(
        self,
        features: AudioFeatures,
        emotion: EmotionPrediction,
    ) -> DepressionIndicators:
        """Extract individual depression risk signals from features."""

        # 1. Emotion valence ratio — proportion of negative emotions
        neg_prob = sum(
            emotion.distribution.get(e, 0.0) for e in NEGATIVE_EMOTIONS
        )
        pos_prob = sum(
            emotion.distribution.get(e, 0.0) for e in POSITIVE_EMOTIONS
        )
        total_prob = neg_prob + pos_prob
        valence_ratio = neg_prob / total_prob if total_prob > 0 else 0.5

        # 2. Energy level — normalize RMS to 0-1 scale
        #    Note: Jitter/Shimmer also affect this now.
        #    Depressed speech often has lower energy variability.
        energy_level = min(1.0, features.rms_energy / 0.15)

        # 3. Pitch variability — low variability = flat affect
        #    Add Jitter (frequency instability) as a multiplier
        if features.pitch_mean and features.pitch_mean > 0:
            pitch_var = min(1.0, (features.pitch_std or 0.0) / features.pitch_mean)
            # Higher jitter (> 0.02) can indicate vocal strain/distress
            if features.jitter > 0.02:
                pitch_var *= 0.8  # further suppress variability score (higher risk)
        else:
            pitch_var = 0.5  # neutral default

        # 4. Speaking rate — approximate from zero crossing rate
        #    Incorporate Shimmer (amplitude instability)
        speaking_rate = min(1.0, features.zero_crossing_rate / 0.15)
        if features.shimmer > 0.05:
            # high shimmer (instability) correlates with tremors/anxiety
            speaking_rate *= 0.9

        # 5. Emotion volatility — std of confidence scores
        if len(self._confidence_history) >= 3:
            volatility = float(np.std(list(self._confidence_history)))
        else:
            volatility = 0.0

        return DepressionIndicators(
            emotion_valence_ratio=valence_ratio,
            energy_level=energy_level,
            pitch_variability=pitch_var,
            speaking_rate_factor=speaking_rate,
            emotion_volatility=volatility,
        )

    @staticmethod
    def _categorize_depression(score: float) -> str:
        """Categorize a 0-100 depression score."""
        if score < 25.0:
            return "Normal"
        elif score < 50.0:
            return "Mild"
        elif score < 75.0:
            return "Moderate"
        else:
            return "Severe"

    # ── Trend Analysis ───────────────────────────────────────────
    def _compute_trend(self) -> str:
        """
        Determine the depression score trend over the recent window.
        Compares the average of the last 5 scores to the previous 5.
        """
        scores = list(self._depression_scores)
        if len(scores) < 6:
            return "stable"

        recent = np.mean(scores[-5:])
        previous = np.mean(scores[-10:-5]) if len(scores) >= 10 else np.mean(scores[:-5])
        diff = recent - previous

        if diff > 3.0:
            return "increasing"
        elif diff < -3.0:
            return "decreasing"
        return "stable"

    def _compute_dominant_emotion(self) -> str:
        """Return the most frequently predicted emotion across the session."""
        if not self._emotion_history:
            return "neutral"

        counts: Dict[str, int] = {}
        for e in self._emotion_history:
            counts[e] = counts.get(e, 0) + 1
        return max(counts, key=counts.get)

    # ── Session Summary ──────────────────────────────────────────
    def get_session_summary(self) -> Dict[str, object]:
        """
        Generate a summary of the entire session's processing results.
        Call this when the session ends.
        """
        scores = list(self._depression_scores)
        emotions = list(self._emotion_history)

        # Emotion distribution across session
        emotion_counts: Dict[str, int] = {}
        for e in emotions:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        total = len(emotions) if emotions else 1
        emotion_dist = {k: round(v / total, 3) for k, v in emotion_counts.items()}

        return {
            "chunks_processed": self._chunks_processed,
            "depression_score_avg": round(np.mean(scores), 2) if scores else 0.0,
            "depression_score_max": round(max(scores), 2) if scores else 0.0,
            "depression_score_min": round(min(scores), 2) if scores else 0.0,
            "depression_score_final": round(scores[-1], 2) if scores else 0.0,
            "depression_category_final": self._categorize_depression(scores[-1]) if scores else "Normal",
            "depression_trend": self._compute_trend(),
            "dominant_emotion": self._compute_dominant_emotion(),
            "emotion_distribution": emotion_dist,
            "avg_rms_energy": (
                round(np.mean(list(self._energy_history)), 6)
                if self._energy_history else 0.0
            ),
        }

    def reset(self) -> None:
        """Clear all rolling state. Call between sessions if reusing the pipeline."""
        self._depression_scores.clear()
        self._emotion_history.clear()
        self._confidence_history.clear()
        self._energy_history.clear()
        self._chunks_processed = 0
        self.diarizer.reset()
        logger.info("AudioPipeline state reset")
