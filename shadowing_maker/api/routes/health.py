"""
Health check routes
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import psutil
from pathlib import Path

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "Video Clipping API",
        "version": "1.0.0"
    }


@router.get("/system/status")
async def system_status():
    """시스템 상태 확인"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count()
        },
        "memory": {
            "percent": memory.percent,
            "available": f"{memory.available / (1024**3):.1f} GB",
            "total": f"{memory.total / (1024**3):.1f} GB"
        },
        "disk": {
            "percent": disk.percent,
            "free": f"{disk.free / (1024**3):.1f} GB",
            "total": f"{disk.total / (1024**3):.1f} GB"
        }
    }


@router.get("/disk/usage")
async def get_disk_usage():
    """디스크 사용량 확인"""
    output_dir = Path("./output")
    
    if not output_dir.exists():
        return {"error": "Output directory not found"}
    
    total_size = 0
    file_count = 0
    
    for file in output_dir.rglob("*"):
        if file.is_file():
            total_size += file.stat().st_size
            file_count += 1
    
    return {
        "output_directory": str(output_dir.absolute()),
        "total_files": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2)
    }