"""
File serving routes
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["files"])

@router.get("/files/download")
async def download_file(path: str):
    """파일 다운로드"""
    try:
        file_path = Path(path)
        
        # 보안: 절대 경로만 허용하고 상위 디렉토리 접근 차단
        if not file_path.is_absolute():
            raise HTTPException(status_code=400, detail="Absolute path required")
            
        if ".." in str(file_path):
            raise HTTPException(status_code=400, detail="Path traversal not allowed")
            
        # 파일 존재 확인
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
            
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
            
        # 허용된 디렉토리 확인
        allowed_dirs = [
            "/home/kang/dev_amd/shadowing_maker_xls/output",
            "/mnt/qnap/media_eng",
            "/mnt/qnap/media_kor"
        ]
        
        if not any(str(file_path).startswith(allowed_dir) for allowed_dir in allowed_dirs):
            logger.error(f"Access denied to: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")
            
        # 파일 반환
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4" if file_path.suffix == ".mp4" else "application/octet-stream",
            filename=file_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))