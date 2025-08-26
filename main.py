#!/usr/bin/env python3
"""
Video Clipping RESTful API - Main Application
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os
import redis
import signal
import sys
from pathlib import Path

# Initialize database
from database import init_db

# Import configuration
from api.config import (
    logger, REDIS_HOST, REDIS_PORT, REDIS_DB,
    ALLOWED_ORIGINS, OUTPUT_DIR
)

# Import utilities
from api.utils import set_redis_client

# Import all routes
from api.routes import (
    health_router,
    clip_router,
    batch_router,
    textbook_router,
    status_router,
    download_router,
    admin_router
)

# Rate limiter initialization
limiter = Limiter(key_func=get_remote_address)

# FastAPI app initialization
app = FastAPI(
    title="Video Clipping API",
    description="Professional video clipping service with subtitle support",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    logger.error(f"Request body: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body)
        }
    )

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Serve frontend files
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/admin", StaticFiles(directory=".", html=True), name="admin")

# Serve output files
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# Include all routers
app.include_router(health_router)
app.include_router(clip_router)
app.include_router(batch_router)
app.include_router(textbook_router)
app.include_router(status_router)
app.include_router(download_router)
app.include_router(admin_router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행되는 이벤트"""
    logger.info("Starting Video Clipping API...")
    
    # Initialize database
    init_db()
    
    # Redis 연결 시도
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=False
        )
        redis_client.ping()
        set_redis_client(redis_client, use_redis=True)
        logger.info(f"Redis connected: {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        logger.warning("Using memory storage for job status")
        set_redis_client(None, use_redis=False)
    
    # Create necessary directories
    OUTPUT_DIR.mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    logger.info("Video Clipping API started successfully")

# Shutdown event
@app.on_event("shutdown") 
async def shutdown_event():
    """서버 종료 시 실행되는 이벤트"""
    logger.info("Shutting down Video Clipping API...")
    
    # Cleanup any active processes
    from api.utils import active_processes, cleanup_job_processes
    for job_id in list(active_processes.keys()):
        cleanup_job_processes(job_id)
    
    logger.info("Video Clipping API shut down")

# Signal handlers
def signal_handler(sig, frame):
    """신호 처리기"""
    logger.info(f"Received signal {sig}")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment or use defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    workers = int(os.getenv("API_WORKERS", "4"))
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=os.getenv("API_RELOAD", "false").lower() == "true"
    )