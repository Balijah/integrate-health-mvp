# Whisper Transcription Service

Self-hosted audio transcription service using OpenAI's Whisper large-v3 model.

## Requirements

- NVIDIA GPU with CUDA support (recommended)
- Python 3.11+
- FFmpeg

## Quick Start

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the service
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8080
```

### Docker

```bash
# Build image
docker build -t whisper-service .

# Run with GPU support
docker run --gpus all -p 8080:8080 whisper-service
```

## API Endpoints

### Health Check

```bash
GET /health

Response:
{
  "status": "healthy",
  "model": "whisper-large-v3",
  "gpu": true,
  "gpu_info": {
    "name": "NVIDIA T4",
    "memory_total_gb": 15.0,
    "memory_allocated_gb": 2.5
  },
  "model_loaded": true
}
```

### Transcribe Audio

```bash
POST /transcribe
Content-Type: multipart/form-data

Form fields:
- audio: Audio file (required)
- mime_type: MIME type string (default: "audio/wav")
- language: Language code (default: "en")

Response:
{
  "text": "Transcribed text here...",
  "duration": 120.5,
  "language": "en",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "First segment text"
    }
  ]
}
```

### Example Usage

```bash
# Using curl
curl -X POST http://localhost:8080/transcribe \
  -F "audio=@recording.wav" \
  -F "mime_type=audio/wav" \
  -F "language=en"

# Using Python
import requests

with open("recording.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8080/transcribe",
        files={"audio": f},
        data={"mime_type": "audio/wav", "language": "en"}
    )
    print(response.json())
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Service port |
| `WHISPER_MODEL` | large-v3 | Whisper model to use |

## Supported Audio Formats

- WAV (audio/wav)
- MP3 (audio/mpeg)
- WebM (audio/webm)
- M4A (audio/mp4)
- OGG (audio/ogg)

## Performance Notes

- **GPU**: With a T4 GPU, transcription runs ~10-15x faster than real-time
- **CPU**: CPU-only mode is significantly slower, not recommended for production
- **Memory**: The large-v3 model requires ~3GB GPU memory

## Deployment

The service is designed to run on AWS EC2 GPU instances (g4dn.xlarge recommended).

See the main project's Terraform configuration for infrastructure setup.
