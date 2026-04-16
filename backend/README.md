# 🎙️ PsychVoice AI Backend Architecture

PsychVoice AI is a clinical-grade, real-time voice emotion detection and multimodal psychiatric analytics engine. Built with FastAPI, PostgreSQL, and deep learning, it natively parses unstructured conversations, extracts clinical manifestations of depression, and rigorously mitigates false positives.

## 🧠 Multimodal Diagnostic Architecture

PsychVoice moves beyond standard voice-emotion models by integrating physics-based gating and semantic analysis to uncover hidden stress.

### 1. Hybrid Emotion Fusion Engine (Acoustic + Text)
A standard diagnostic vulnerability is "Masked Depression," where a patient verbally states they are struggling but maintains a flat, unemotional prosody. To counter this:
- **Acoustic Sub-system**: `facebook/wav2vec2-large-robust` extracts tonality and prosody from the wav signal.
- **Linguistic Sub-system**: `openai/whisper-base` runs zero-latency transcription, while `j-hartmann/emotion-english-distilroberta-base` parses the semantic transcript for emotional distress.
- **Dynamic Override**: If the transcript explicitly contains high-stress markers (Sadness, Fear > 40%) but the acoustic layer detects "Neutral" or "Happy", the system mathematically penalizes the voice model and forces the text analysis to dominate 80% of the voting weight.

### 2. Physical Acoustic Gating (The "Happy" Crusher)
To eliminate "actor domain shift" (where AI mislabels tense or strained breathing as "Happy"), the inference stream implements a hard physics override:
- The system extracts raw **Spectral Centroid** (tone darkness/brightness) and **ZCR (Zero-Crossing-Rate)** (vocal tension/breathiness) via Librosa.
- **Clinical Rule**: If a voice exhibits physical darkness (`< 1500Hz`) or high tension (`ZCR > 10%`), the mathematical probability of "Happy" or "Calm" is forcefully multiplied by `0.10` (crushed), bubbling underlying anxiety to the top.

### 3. Patient Isolation (Speaker Diarization)
PsychVoice implements `pyannote.audio` Speaker Diarization into the live ingestion stream.
- The pipeline scans the 3-second audio windows, isolating multiple speakers.
- It dynamically identifies the primary speaker ("Doctor" vs "Patient") based on the timeline.
- Emotion extraction is rigorously skipped during the clinician's turn to prevent non-patient data from skewing the session's overall Depression Score.

### 4. Clinical Baseline Suppression (EMA)
In modern psychiatry, "Neutral" is not an actionable diagnosis. PsychVoice suppresses "Neutral" and "Calm" outputs by heavily penalizing their final softmax values by 65%. 
Combined with Exponential Moving Average (EMA) smoothing over a rolling time window, this ensures that fleeting moments of subtle distress build up to a cumulative, highly accurate Clinical Risk Index.

---

## 🛠️ Tech Stack & Infrastructure

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115+ |
| ML Pipeline | Wav2Vec2, Whisper, DistilRoBERTa, Pyannote |
| Signal Processing | Librosa, Numpy, Spectral Gating (Noisereduce) |
| Database | PostgreSQL 16 + asyncpg |
| ORM / Persistence | SQLAlchemy 2.0 (async), Alembic |
| Real-time | Binary WebSocket Streaming |

## 🚀 Quick Start & Integration

### Option A: Docker Compose (recommended)
```bash
# Start PostgreSQL + API
docker compose up -d

# API is live at http://localhost:8000
```

### Option B: Local Development
```bash
# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Environment Config (CRITICAL)
# Add your huggingface token to .env for the Speaker Diarization to activate!
echo "HF_AUTH_TOKEN=your_hf_token_here" > .env

# 4. Start the Application
uvicorn app.main:app --reload --port 8000
```

---

## 🔌 API Endpoints
*Full documentation available dynamically at `localhost:8000/docs`*

### AI & Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws/session/{session_id}` | Real-time audio stream & AI inference stream |
| POST | `/api/v1/sessions` | Create a new session or upload offline `.opus` recordings |
| GET | `/api/v1/sessions/{id}/frames` | Retrieve all processed ML inference frames (with transcript logs) |

### Core Infrastructure
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | JWT Authentication & Login |
| GET | `/api/v1/patients` | Patient roster fetching |

## License
MIT
