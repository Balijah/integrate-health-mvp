"""
FastAPI application entry point.

Configures the app with CORS, routes, and health check endpoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="HIPAA-compliant AI assistant for functional medicine documentation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
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
from app.api import auth, visits

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(visits.router, prefix="/api/v1/visits", tags=["visits"])

# Future routes (will be added in later phases)
# from app.api import notes
# app.include_router(notes.router, prefix="/api/v1/notes", tags=["notes"])
