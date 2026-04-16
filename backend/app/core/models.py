import asyncio
import logging
from typing import Optional

from app.services.diarization_service import DiarizationService
from app.services.hybrid_emotion import HybridEmotionEngine
from app.services.inference_bridge import Wav2Vec2EmotionModel, InferenceModel

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Singleton manager for heavy ML models.
    Pre-loading these during application startup prevents 'stuck' connections
    during the first clinician session.
    """
    _emotion_model: Optional[InferenceModel] = None
    _diarizer: Optional[DiarizationService] = None
    _hybrid: Optional[HybridEmotionEngine] = None
    _ready: bool = False

    @classmethod
    async def load_models(cls):
        """Pre-load all models into memory/GPU in a background thread."""
        if cls._ready:
            logger.info("Models already loaded and ready.")
            return

        logger.info("--- Starting AI Model Pre-load (Background) ---")
        
        try:
            # Load models in a separate thread to avoid blocking the event loop
            def _init_sync():
                # 1. Load Acoustic Emotion Model (Wav2Vec2)
                emo = Wav2Vec2EmotionModel()
                # 2. Load Diarization Service
                dia = DiarizationService(sample_rate=16000)
                # 3. Load Hybrid Engine (Whisper ASR + DistilRoBERTa text emotion)
                hybrid = HybridEmotionEngine()
                return emo, dia, hybrid

            cls._emotion_model, cls._diarizer, cls._hybrid = await asyncio.to_thread(_init_sync)
            cls._ready = True
            logger.info("--- AI Model Warming Complete: Engine Ready (Hybrid Mode) ---")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to pre-load AI models: {e}", exc_info=True)
            cls._ready = False

    @classmethod
    def is_ready(cls) -> bool:
        """Check if models are fully initialized and ready for inference."""
        return cls._ready

    @classmethod
    def get_emotion_model(cls) -> InferenceModel:
        if not cls._emotion_model:
            logger.warning("Emotion model accessed before loading. Using fallback instance (blocking!).")
            cls._emotion_model = Wav2Vec2EmotionModel()
        return cls._emotion_model

    @classmethod
    def get_diarizer(cls) -> DiarizationService:
        if not cls._diarizer:
            logger.warning("Diarizer accessed before loading. Using fallback instance (blocking!).")
            cls._diarizer = DiarizationService(sample_rate=16000)
        return cls._diarizer

    @classmethod
    def get_hybrid_engine(cls) -> Optional[HybridEmotionEngine]:
        """Returns the hybrid engine if loaded, None otherwise (pipeline gracefully degrades)."""
        return cls._hybrid

model_manager = ModelManager()
