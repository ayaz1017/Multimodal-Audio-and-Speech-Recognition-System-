"""
Hybrid Multimodal Emotion Recognition Engine.

Combines two independent emotion signals and fuses them:
  1. ACOUSTIC branch  — Wav2Vec2 reads prosody, pitch, energy directly from the waveform
  2. LINGUISTIC branch — Whisper transcribes speech → DistilRoBERTa classifies the words

Fusion Strategy (Late Fusion Weighted Average):
  final_distribution = α * acoustic + (1-α) * linguistic
  default α = 0.6  (acoustic slightly dominates: voice is more honest than words)

Clinical rationale: A depressed patient may say "I'm fine" (neutral text)
but their voice carries slow speech rate, flat pitch, breathiness (sad acoustic).
The hybrid correctly identifies the masked depression the text alone would miss.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Label alignment between the two models ───────────────────────────────────
# Hartmann DistilRoBERTa outputs 7 classes; we map them to our 8 canonical labels.
TEXT_TO_ACOUSTIC_LABEL_MAP = {
    "anger":    "anger",
    "disgust":  "disgust",
    "fear":     "fear",
    "joy":      "happy",
    "neutral":  "neutral",
    "sadness":  "sad",
    "surprise": "surprise",
}

# Labels present in acoustic but not text model — will receive only acoustic signal
ACOUSTIC_ONLY_LABELS = {"calm"}

# Canonical 8 classes
ALL_LABELS = ["neutral", "calm", "happy", "sad", "anger", "fear", "disgust", "surprise"]


class HybridEmotionEngine:
    """
    Loads and manages the ASR (Whisper) and text emotion (DistilRoBERTa) models.
    Designed to be used alongside the existing Wav2Vec2EmotionModel.
    """

    def __init__(
        self,
        asr_model: str = "openai/whisper-base",
        text_model: str = "j-hartmann/emotion-english-distilroberta-base",
        acoustic_weight: float = 0.60,   # Weight for acoustic branch (0-1)
    ):
        self.acoustic_weight = acoustic_weight
        self.linguistic_weight = 1.0 - acoustic_weight
        self._asr_loaded = False
        self._text_loaded = False
        self._asr = None
        self._text_clf = None

        try:
            from transformers import pipeline
            import torch

            # ── ASR: Whisper-base ─────────────────────────────────────────────
            logger.info("Loading Whisper ASR: %s", asr_model)
            t0 = time.perf_counter()
            self._asr = pipeline(
                "automatic-speech-recognition",
                model=asr_model,
                device="cpu",        # Force CPU — Whisper MPS has a known int32 bug in transformers<4.40
                chunk_length_s=30,
                generate_kwargs={"language": "en", "task": "transcribe"},
            )
            self._asr_loaded = True
            logger.info("Whisper loaded in %.1fs", time.perf_counter() - t0)

            # ── Text Emotion: DistilRoBERTa ──────────────────────────────────
            logger.info("Loading text emotion model: %s", text_model)
            t0 = time.perf_counter()

            device_id = -1  # default CPU
            try:
                if torch.backends.mps.is_available():
                    device_id = "mps"
                elif torch.cuda.is_available():
                    device_id = 0
            except Exception:
                pass

            self._text_clf = pipeline(
                "text-classification",
                model=text_model,
                top_k=None,          # Return all class scores
                device=device_id,
            )
            self._text_loaded = True
            logger.info("Text emotion model loaded in %.1fs", time.perf_counter() - t0)

        except Exception as e:
            logger.error("HybridEmotionEngine failed to load: %s", e)

    @property
    def is_ready(self) -> bool:
        return self._asr_loaded and self._text_loaded

    def transcribe(self, audio: np.ndarray) -> str:
        """Run Whisper ASR on a 16kHz float32 audio array. Returns transcript text."""
        if not self._asr_loaded or self._asr is None:
            return ""
        
        # Whisper hallucinations often trigger on background noise/breathing.
        # We blacklist these common 'trash' outputs.
        HALLUCINATION_BLACKLIST = {
            "music", "you", "thanks for watching", "thank you", "bye", 
            "please subscribe", "be right back", "hi", "mhm", "uh-huh"
        }

        try:
            result = self._asr({"array": audio, "sampling_rate": 16000})
            text = result.get("text", "").strip()
            
            # Filter hallucinations and extremely short noise-bursts
            clean_text = text.lower().strip(" .?!,")
            if clean_text in HALLUCINATION_BLACKLIST or len(clean_text) < 2:
                return ""
            
            return text
        except Exception as e:
            logger.warning("Whisper transcription failed: %s", e)
            return ""

    def text_emotion_distribution(self, text: str) -> Dict[str, float]:
        """
        Run DistilRoBERTa on the transcribed text.
        Returns a probability distribution over our 8 canonical labels.
        """
        dist = {label: 0.0 for label in ALL_LABELS}

        if not self._text_loaded or not text or len(text.split()) < 2:
            # Not enough text to make a reliable prediction — return uniform
            # so it doesn't bias the fusion
            for k in dist:
                dist[k] = 1.0 / len(ALL_LABELS)
            return dist

        try:
            raw = self._text_clf(text)[0]  # list of {label, score}
            for item in raw:
                canonical = TEXT_TO_ACOUSTIC_LABEL_MAP.get(item["label"].lower())
                if canonical and canonical in dist:
                    dist[canonical] += item["score"]

            # calm gets no signal from text model — give it a small smoothing prior
            dist["calm"] = 0.02

            total = sum(dist.values())
            if total > 0:
                dist = {k: v / total for k, v in dist.items()}
        except Exception as e:
            logger.warning("Text emotion classification failed: %s", e)
            # On error return uniform
            for k in dist:
                dist[k] = 1.0 / len(ALL_LABELS)

        return dist

    def fuse(
        self,
        acoustic_distribution: Dict[str, float],
        text_distribution: Dict[str, float],
        transcript: str = "",
    ) -> Dict[str, float]:
        """
        Late-fusion weighted average of acoustic and linguistic distributions.
        Dynamically shifts weights based on clinical priorities.
        """
        # Dynamic Weighting Logic: The Clinical Override
        # If the transcript shows heavy stress/depression, but the acoustic model 
        # (trained on actors) is confused and guessing Neutral/Happy, we trust the words.
        a_weight = self.acoustic_weight
        t_weight = self.linguistic_weight

        text_stress = text_distribution.get("sad", 0.0) + text_distribution.get("fear", 0.0)
        acoustic_happy = acoustic_distribution.get("happy", 0.0)
        acoustic_neutral = acoustic_distribution.get("neutral", 0.0) + acoustic_distribution.get("calm", 0.0)

        # If text is stressed (>40%) and voice is missing it, invert weights (80% text, 20% acoustic)
        if text_stress > 0.40 and (acoustic_happy > 0.30 or acoustic_neutral > 0.40):
            a_weight = 0.20
            t_weight = 0.80

        fused = {}
        for label in ALL_LABELS:
            a = acoustic_distribution.get(label, 0.0)
            t = text_distribution.get(label, 0.0)
            fused[label] = a_weight * a + t_weight * t

        # ── Clinical Baseline Suppression ────────────────────────
        # In psychiatric screening, "neutral/calm" is the default resting state.
        # It typically completely masks subtle signs of stress. 
        # By heavily suppressing the baseline, we force underlying valences to surface.
        fused["neutral"] *= 0.35
        fused["calm"]    *= 0.35

        # Re-normalize
        total = sum(fused.values())
        if total > 0:
            fused = {k: v / total for k, v in fused.items()}

        return fused
