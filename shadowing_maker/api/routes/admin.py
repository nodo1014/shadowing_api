"""
Admin routes for system management
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pathlib import Path
import logging
import sys
import os

# Import from adapter
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from database_adapter import (
    get_statistics, cleanup_old_jobs, delete_jobs_bulk,
    get_recent_jobs, get_job_by_id, delete_job
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/statistics")
async def get_system_statistics():
    """시스템 통계 조회"""
    try:
        stats = get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_orphaned_records():
    """파일이 없는 DB 레코드 정리"""
    try:
        jobs = get_recent_jobs(limit=1000)
        deleted_count = 0
        
        for job in jobs:
            if job.get("output_file"):
                # 파일 존재 확인
                if not os.path.exists(job["output_file"]):
                    # 파일이 없으면 DB에서 삭제
                    from database import delete_job
                    if delete_job(job["id"]):
                        deleted_count += 1
                        logger.info(f"Deleted orphaned job: {job['id']}")
        
        return {
            "message": "Cleanup completed",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/bulk")
async def delete_jobs_bulk_endpoint(job_ids: list[str]):
    """여러 작업 일괄 삭제"""
    try:
        if not job_ids:
            raise HTTPException(status_code=400, detail="No job IDs provided")
        
        success_count = 0
        failed_ids = []
        
        for job_id in job_ids:
            try:
                # 작업 정보 조회
                job_data = get_job_by_id(job_id)
                
                # 파일 삭제 시도
                if job_data and job_data.get("output_file"):
                    output_path = Path(job_data["output_file"])
                    if output_path.exists():
                        if output_path.is_dir():
                            import shutil
                            shutil.rmtree(output_path)
                        else:
                            output_path.unlink()
                
                # DB에서 삭제
                if delete_job(job_id):
                    success_count += 1
                else:
                    failed_ids.append(job_id)
                    
            except Exception as e:
                logger.warning(f"Failed to delete job {job_id}: {e}")
                failed_ids.append(job_id)
        
        return {
            "message": f"Deleted {success_count} jobs",
            "success_count": success_count,
            "failed_ids": failed_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/old")
async def cleanup_old_jobs_endpoint(days: int = Query(30, ge=1, le=365)):
    """오래된 작업 정리"""
    try:
        deleted_count = cleanup_old_jobs(days)
        return {
            "message": f"Cleaned up jobs older than {days} days",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_system_config():
    """시스템 설정 조회"""
    try:
        config = {
            "output_directory": str(Path("./output").absolute()),
            "database_path": str(Path("./clipping.db").absolute()),
            "max_file_size_mb": 5000,
            "supported_formats": ["mp4", "mkv", "avi", "mov"],
            "template_count": 3,
            "clipping_types": 2
        }
        return config
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))