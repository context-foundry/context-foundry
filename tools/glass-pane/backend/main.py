"""
Glass Pane Backend - FastAPI Application Entry Point

Real-time visualization dashboard for Context Foundry autonomous builds.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api import (
    jobs_router,
    logs_router,
    files_router,
    sse_router,
    artifacts_router,
    chat_router,
    builds_router,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Glass Pane backend starting...")
    logger.info(f"Database: {settings.expanded_db_path}")
    logger.info(f"Watch path: {settings.expanded_watch_path}")
    logger.info(f"CORS origins: {settings.cors_origins}")

    yield

    # Shutdown
    logger.info("Glass Pane backend shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Glass Pane API",
    description="Real-time visualization dashboard for Context Foundry builds",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(jobs_router)
app.include_router(logs_router)
app.include_router(files_router)
app.include_router(sse_router)
app.include_router(artifacts_router)
app.include_router(chat_router)
app.include_router(builds_router)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "service": "Glass Pane API",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": str(settings.expanded_db_path),
        "watch_path": str(settings.expanded_watch_path),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
