"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import logging

# Import routers
from .routes import health, job, clip, batch, admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Video Clipping API",
        description="Professional video clipping service with subtitle support",
        version="2.0.0",  # Refactored version
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )
    
    # CORS middleware
    allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router)
    app.include_router(job.router)
    app.include_router(clip.router)
    app.include_router(batch.router)
    app.include_router(admin.router)
    
    # Mount static files if directories exist
    frontend_path = Path(__file__).parent.parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")
    
    # Root redirect
    @app.get("/")
    async def root():
        return {"message": "Video Clipping API v2.0", "docs": "/api/docs"}
    
    # Startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting Video Clipping API v2.0")
        
        # Ensure output directory exists
        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)
        
        # Initialize database
        try:
            import sys
            sys.path.append(str(Path(__file__).parent.parent.parent))
            from database import init_db
            init_db()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down Video Clipping API")
    
    return app


# Create app instance
app = create_app()