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
from .youtube_viewer import router as youtube_viewer_router
from .file_management import router as file_management_router
from .intro import router as intro_router

__all__ = [
    'health_router',
    'clip_router', 
    'batch_router',
    'mixed_router',
    'extract_router',
    'status_router',
    'download_router',
    'admin_router',
    'youtube_viewer_router',
    'file_management_router',
    'intro_router'
]