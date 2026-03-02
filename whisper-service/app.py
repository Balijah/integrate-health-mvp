"""
Whisper Transcription Service.

A standalone FastAPI service for audio transcription using OpenAI's Whisper model.
Designed to run on GPU instances for optimal performance.
"""

import logging
import os
import tempfile
from typing import Optional

import torch
import whisper
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Whisper Transcription Service",
    description="Self-hosted audio transcription using Whisper large-v3",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model variable
model: Optional[whisper.Whisper] = None


def get_extension_from_mime(mime_type: str) -> str:
    """Get file extension from MIME type."""
    extensions = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp3": ".mp3",
        "audio/mpeg": ".mp3",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/ogg": ".ogg",
    }
    return extensions.get(mime_type, ".wav")


@app.on_event("startup")
def load_model():
    """Load the Whisper model on startup."""
    global model

    logger.info("Starting Whisper service...")
    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        device = "cuda"
    else:
        logger.warning("CUDA not available, using CPU (this will be slow)")
        device = "cpu"

    # Load model
    model_name = os.environ.get("WHISPER_MODEL", "large-v3")
    logger.info(f"Loading Whisper model: {model_name}")

    try:
        model = whisper.load_model(model_name, device=device)
        logger.info(f"Whisper model loaded successfully on {device}")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        raise


@app.get("/health")
def health():
    """Health check endpoint."""
    gpu_info = None
    if torch.cuda.is_available():
        gpu_info = {
            "name": torch.cuda.get_device_name(0),
            "memory_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
            "memory_allocated_gb": round(torch.cuda.memory_allocated(0) / 1e9, 2),
        }

    return {
        "status": "healthy",
        "model": "whisper-large-v3",
        "gpu": torch.cuda.is_available(),
        "gpu_info": gpu_info,
        "model_loaded": model is not None,
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    mime_type: str = Form("audio/wav", description="MIME type of the audio file"),
    language: str = Form("en", description="Language code (e.g., 'en', 'es', 'fr')"),
):
    """
    Transcribe an audio file.

    Args:
        audio: The audio file to transcribe.
        mime_type: MIME type of the audio file.
        language: Language code for transcription.

    Returns:
        Transcription result with text, duration, and segments.
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Whisper model not loaded. Service is starting up.",
        )

    # Get file extension
    ext = get_extension_from_mime(mime_type)

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        try:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

            logger.info(f"Transcribing audio file: {len(content)} bytes, type: {mime_type}")

            # Transcribe with Whisper
            result = model.transcribe(
                tmp_path,
                language=language,
                fp16=torch.cuda.is_available(),  # Use FP16 on GPU for speed
                verbose=False,
            )

            logger.info(f"Transcription completed: {len(result.get('text', ''))} characters")

            # Extract segments for detailed timing info
            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "id": seg.get("id"),
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text", "").strip(),
                })

            return {
                "text": result.get("text", "").strip(),
                "duration": result.get("duration", 0),
                "language": result.get("language", language),
                "segments": segments,
            }

        except Exception as e:
            logger.error(f"Transcription failed: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {str(e)}",
            )

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.get("/")
def root():
    """Root endpoint with service info."""
    return {
        "service": "Whisper Transcription Service",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/transcribe": "Transcribe audio (POST)",
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
