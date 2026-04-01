"""
FastAPI application entry point.

Configures the app with CORS, routes, and health check endpoint.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings

settings = get_settings()

# Create rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="HIPAA-compliant AI assistant for functional medicine documentation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limiter to app state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS - include production domains
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
    # Production origins
    "https://app.integratehealth.ai",
    "https://d3nem3tkboqfr7.cloudfront.net",
    "http://integrate-health-alb-32268964.us-east-1.elb.amazonaws.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict:
    """
    Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {
        "message": "Welcome to Integrate Health API",
        "docs": "/docs",
        "health": "/health",
    }


# API routes
from app.api import auth, visits, transcription, notes, websockets, support, summary, password_reset, profile

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(visits.router, prefix="/api/v1/visits", tags=["visits"])
app.include_router(transcription.router, prefix="/api/v1/visits", tags=["transcription"])
app.include_router(notes.router, prefix="/api/v1/visits", tags=["notes"])
app.include_router(support.router, prefix="/api/v1", tags=["support"])
app.include_router(summary.router, prefix="/api/v1/visits", tags=["summary"])
app.include_router(password_reset.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/v1", tags=["profile"])

# WebSocket routes (no prefix - uses /ws/*)
app.include_router(websockets.router, tags=["websockets"])
