"""
Abstract ML inference bridge.

Defines the interface that any emotion/depression model must implement,
along with a placeholder implementation that returns mock predictions.
Swap in a real model (wav2vec2, custom CNN, etc.) by subclassing InferenceModel.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

try:
    import torch
    from transformers import Wav2Vec2ForSequenceClassification, AutoFeatureExtractor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EmotionPrediction:
    """Result from an emotion classification model."""
    label: str                             # Primary emotion: "sad", "happy", etc.
    confidence: float                      # Probability of the primary label
    distribution: Dict[str, float]         # Full probability distribution
    entropy: float = 0.0                   # Shannon entropy (measure of uncertainty)
    inference_time_ms: float = 0.0         # Time taken for inference

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "distribution": {k: round(v, 4) for k, v in self.distribution.items()},
            "entropy": round(self.entropy, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
        }


@dataclass
class DepressionIndicators:
    """Intermediate depression risk signals extracted from audio features."""
    emotion_valence_ratio: float       # negative / total emotions (0-1)
    energy_level: float                # normalized RMS (0-1, low = depressive)
    pitch_variability: float           # F0 std / F0 mean (0-1, low = flat affect)
    speaking_rate_factor: float        # relative to baseline (0-1)
    emotion_volatility: float          # std of emotion confidence over window

    def to_dict(self) -> Dict[str, float]:
        return {
            "emotion_valence_ratio": round(self.emotion_valence_ratio, 4),
            "energy_level": round(self.energy_level, 4),
            "pitch_variability": round(self.pitch_variability, 4),
            "speaking_rate_factor": round(self.speaking_rate_factor, 4),
            "emotion_volatility": round(self.emotion_volatility, 4),
        }


# ── Abstract Base ────────────────────────────────────────────────
class InferenceModel(ABC):
    """
    Abstract interface for ML models. Implement this to plug in any
    emotion detection or depression scoring model.
    """

    @abstractmethod
    def predict_emotion(
        self,
        audio: np.ndarray,
        features: Optional[np.ndarray] = None,
    ) -> EmotionPrediction:
        """
        Predict the emotion from audio and/or extracted features.

        Args:
            audio: Raw audio array (1D float32).
            features: Optional pre-extracted feature vector.

        Returns:
            EmotionPrediction with label, confidence, and distribution.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if the model is loaded and ready for inference."""
        ...


# ── Placeholder Implementation ───────────────────────────────────
class PlaceholderEmotionModel(InferenceModel):
    """
    Mock emotion model for development and testing.

    Uses simple heuristics on audio features to produce plausible
    (but not accurate) emotion predictions. Replace with a real model
    (wav2vec2, HuBERT, etc.) for production use.

    The heuristic logic:
      - Low energy + low pitch variability → "sad"
      - High energy + high zero-crossing rate → "angry"
      - Moderate energy + moderate pitch → "neutral" or "calm"
      - High pitch + high energy → "happy"
    """

    EMOTION_LABELS = [
        "angry", "calm", "disgust", "fearful",
        "happy", "neutral", "sad", "surprised",
    ]

    def __init__(self):
        self._loaded = True
        logger.info(
            "PlaceholderEmotionModel initialized — "
            "replace with a real model for production"
        )

    def predict_emotion(
        self,
        audio: np.ndarray,
        features: Optional[np.ndarray] = None,
    ) -> EmotionPrediction:
        """
        Generate a heuristic-based emotion prediction from audio features.
        """
        start = time.perf_counter()

        if features is not None and len(features) >= 34:
            # Use extracted features if available
            rms = features[30]        # rms_energy position in feature vector
            zcr = features[29]        # zero_crossing_rate position
            pitch_m = features[32]    # pitch_mean position
            pitch_s = features[33]    # pitch_std position
        else:
            # Compute basic features directly from audio
            rms = float(np.sqrt(np.mean(audio ** 2)))
            zcr = float(np.mean(np.abs(np.diff(np.sign(audio))) > 0))
            pitch_m = 150.0  # default estimate
            pitch_s = 30.0

        # Heuristic scoring for each emotion
        scores = {
            "sad":       max(0, (0.3 - rms) * 3 + (50 - pitch_s) * 0.01),
            "angry":     max(0, (rms - 0.15) * 3 + (zcr - 0.1) * 2),
            "happy":     max(0, (rms - 0.05) * 1.5 + (pitch_s - 30) * 0.02),
            "fearful":   max(0, (pitch_s - 40) * 0.03 + (zcr - 0.08) * 1.5),
            "calm":      max(0, 0.5 - abs(rms - 0.05) * 5),
            "neutral":   0.3,  # baseline prior
            "surprised": max(0, (pitch_m - 200) * 0.005 + (rms - 0.1) * 2),
            "disgust":   max(0, (zcr - 0.15) * 1.5 - rms * 0.5),
        }

        # Normalize to a probability distribution first
        total = sum(scores.values())
        if total > 0:
            distribution = {k: v / total for k, v in scores.items()}
        else:
            distribution = {k: 1.0 / len(scores) for k in scores}

        # Calculate entropy: -sum(p * log(p))
        entropy = -sum(p * np.log(p + 1e-9) for p in distribution.values())

        # Find primary label
        primary = max(distribution, key=distribution.get)
        confidence = distribution[primary]

        elapsed = (time.perf_counter() - start) * 1000

        return EmotionPrediction(
            label=primary,
            confidence=confidence,
            distribution=distribution,
            entropy=float(entropy),
            inference_time_ms=elapsed,
        )

    def is_loaded(self) -> bool:
        return self._loaded


# ── Wav2Vec2 Implementation ──────────────────────────────────────
class Wav2Vec2EmotionModel(InferenceModel):
    """
    High-fidelity emotion model using ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition.
    
    This model natively predicts 8 classes (RAVDESS scale):
    - neutral, calm, happy, sad, angry, fearful, disgust, surprised
    """
    
    # Keep label mapping clean and separate — neutral maps to neutral, calm to calm.
    # This avoids probability loss when summing multiple raw labels.
    LABEL_MAPPING = {
        "neutral":   "neutral",
        "calm":      "calm",
        "happy":     "happy",
        "sad":       "sad",
        "angry":     "anger",
        "fearful":   "fear",
        "disgust":   "disgust",
        "surprised": "surprise",
        # SUPERB / IEMOCAP classes
        "neu": "neutral",
        "hap": "happy",
        "ang": "anger"
    }

    # Display names for the 8 semantic classes
    ALL_LABELS = ["neutral", "calm", "happy", "sad", "anger", "fear", "disgust", "surprise"]

    def __init__(self, model_id: str = "r-f/wav2vec-english-speech-emotion-recognition"):
        self._loaded = False
        
        if not TRANSFORMERS_AVAILABLE:
            logger.error("transformers or torch not installed. Cannot load Wav2Vec2.")
            return
            
        try:
            logger.info("Loading Wav2Vec2 emotion model: %s", model_id)
            start = time.perf_counter()
            
            # Load feature extractor and model
            self.processor = AutoFeatureExtractor.from_pretrained(model_id)
            
            # Determine platform-optimal dtype (FP16 for GPU/MPS)
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                self.dtype = torch.float16
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = torch.device("mps")
                self.dtype = torch.float16
            else:
                self.device = torch.device("cpu")
                self.dtype = torch.float32 # CPU usually prefers float32 or bfloat16
                
            self.model = Wav2Vec2ForSequenceClassification.from_pretrained(
                model_id,
                torch_dtype=self.dtype
            )
            self.model.to(self.device)
            self.model.eval() 
            
            # Map model output indices to our semantic labels
            self.id2label = self.model.config.id2label
            self._loaded = True
            
            logger.info("Wav2Vec2 model loaded on %s in %.2fs", 
                        self.device, time.perf_counter() - start)
        except Exception as e:
            logger.error("Failed to load Wav2Vec2 model: %s", e)

    def predict_emotion(
        self,
        audio: np.ndarray,
        features: Optional[np.ndarray] = None,
    ) -> EmotionPrediction:
        """
        Run inference using the transformer model over the audio array.
        """
        start = time.perf_counter()
        
        if not self._loaded:
            logger.warning("Wav2Vec2 model not loaded. Returning neutral.")
            return self._fallback_prediction()
            
        # Ensure 1D audio
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] > 1 else audio[0]

        # ── Raw Acoustic Physics Extraction ──────────────────────
        # Calculate exactly how the patient physically speaks BEFORE we normalize the volume.
        # This gives us hard physics to override the AI's guesses.
        raw_rms = float(np.sqrt(np.mean(audio ** 2)))
        
        # ZCR (Vocal tension/breathiness)
        zcr = float(np.mean(np.diff(np.sign(audio)) != 0)) if len(audio) > 1 else 0.0
        
        # Spectral Centroid (Tone 'Darkness'/'Brightness')
        # Dark tone = <1500Hz (sad/flat), Bright tone = >2500Hz (happy/excited)
        try:
            import librosa
            centroid_arr = librosa.feature.spectral_centroid(y=audio, sr=16000)
            spectral_centroid = float(np.mean(centroid_arr))
        except Exception:
            spectral_centroid = 2000.0

        # ── Audio Pre-processing for Precision ───────────────────
        # 1. Peak normalization: ensure consistent loudness for model stability
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.9  # Normalize to 90% peak to avoid clipping

        # 3. Ensure float32 (required by processor)
        audio = audio.astype(np.float32)

        try:
            # Prepare inputs - processor always requires float32
            inputs = self.processor(
                audio,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            )

            # Move to device — match the model's parameter dtype
            inputs = {
                k: v.to(device=self.device, dtype=self.dtype if v.is_floating_point() else None)
                for k, v in inputs.items()
            }

            # ── Inference: standard softmax, no temperature distortion ──
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.nn.functional.softmax(logits.float(), dim=-1)[0]

            probs_np = probs.cpu().numpy().astype(np.float64)

            # ── Map raw labels → semantic labels (SUMMING, not max) ──
            distribution: dict = {label: 0.0 for label in self.ALL_LABELS}
            for i, p in enumerate(probs_np):
                raw_label = self.id2label[i]
                semantic_label = self.LABEL_MAPPING.get(raw_label, raw_label)
                if semantic_label in distribution:
                    distribution[semantic_label] += float(p)

            # ── HARD ACOUSTIC PHYSICS GATE ───────────────────────────
            # The AI model was trained on actors. We now override it with real clinical physics.
            
            # Rule 1: Whisper Volume Penalty
            # High-arousal modes (anger, happy, surprise) are physically impossible 
            # if the un-normalized RMS is near silence (< 0.005)
            if raw_rms < 0.005:
                distribution["anger"]   *= 0.05
                distribution["happy"]   *= 0.05
                distribution["surprise"] *= 0.10

            # Rule 2: The "Happy" False-Positive Crusher (Tone & Tension)
            # If the patient's tone is physically "Dark" (< 1500Hz) or highly tense/breathy (ZCR > 0.10)
            # it is impossible for them to be genuinely "Happy". 
            if spectral_centroid < 1500 or zcr > 0.10:
                distribution["happy"] *= 0.10
                distribution["calm"]  *= 0.50  # Also suppress calm if highly tense
                
            # Rule 3: Stress/Anxiety Multiplier
            # If tone is dark and tension is high, this is the exact physical signature of masked depression/anxiety.
            if spectral_centroid < 1500 and zcr > 0.08:
                distribution["sad"]  *= 1.5
                distribution["fear"] *= 1.5

            # Re-normalize to sum=1.0
            total = sum(distribution.values())
            if total > 0:
                distribution = {k: v / total for k, v in distribution.items()}

            # ── Shannon entropy of distribution ───────────────────
            entropy = -sum(p * np.log(p + 1e-9) for p in distribution.values())

            # ── Primary emotion ──
            primary = max(distribution, key=distribution.get)
            confidence = distribution[primary]

            elapsed = (time.perf_counter() - start) * 1000

            return EmotionPrediction(
                label=primary,
                confidence=confidence,
                distribution=distribution,
                entropy=float(entropy),
                inference_time_ms=elapsed,
            )
            
        except Exception as e:
            logger.error("Wav2Vec2 inference failed: %s", e)
            return self._fallback_prediction()
            
    def is_loaded(self) -> bool:
        return self._loaded
        
    def _fallback_prediction(self) -> EmotionPrediction:
        """Fallback when the model fails or isn't loaded."""
        dist = {l: 0.0 for l in set(self.LABEL_MAPPING.values())}
        dist["calm"] = 1.0
        return EmotionPrediction(
            label="calm",
            confidence=1.0,
            distribution=dist,
            inference_time_ms=0.0
        )
