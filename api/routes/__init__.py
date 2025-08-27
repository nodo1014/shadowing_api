"""
API Routes Package
"""
from .health import router as health_router
from .clip import router as clip_router
from .batch import router as batch_router
from .mixed import router as mixed_router
from .extract import router as extract_router
from .status import router as status_router
from .download import router as download_router
from .admin import router as admin_router

__all__ = [
    'health_router',
    'clip_router', 
    'batch_router',
    'mixed_router',
    'extract_router',
    'status_router',
    'download_router',
    'admin_router'
]