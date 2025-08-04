"""
Job management routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from typing import Optional, List
from pathlib import Path
import os
import logging

# Import from adapter
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from database_adapter import get_job_by_id, update_job_status, delete_job, get_recent_jobs, search_jobs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """작업 상태 조회"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "id": job_data["id"],
            "status": job_data["status"],
            "progress": job_data.get("progress", 0),
            "message": job_data.get("message", ""),
            "output_file": job_data.get("output_file"),
            "error": job_data.get("error"),
            "created_at": job_data.get("created_at"),
            "completed_at": job_data.get("completed_at")
        }
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/job/{job_id}")
async def delete_job_endpoint(job_id: str, force: bool = Query(False)):
    """작업 삭제"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data and not force:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # 파일 삭제 시도
        if job_data and job_data.get("output_file"):
            output_path = Path(job_data["output_file"])
            if output_path.exists():
                try:
                    output_path.unlink()
                    logger.info(f"Deleted output file: {output_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")
                    if not force:
                        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
        
        # DB에서 삭제
        if delete_job(job_id):
            return {"message": "Job deleted successfully"}
        elif force:
            return {"message": "Job record removed from database"}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{job_id}")
async def download_output(job_id: str):
    """작업 결과 파일 다운로드"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        output_file = job_data.get("output_file")
        if not output_file or not os.path.exists(output_file):
            raise HTTPException(status_code=404, detail="Output file not found")
        
        return FileResponse(
            path=output_file,
            media_type="video/mp4",
            filename=os.path.basename(output_file)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/{job_id}")
async def stream_video(job_id: str):
    """비디오 스트리밍"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        output_file = job_data.get("output_file")
        if not output_file or not os.path.exists(output_file):
            raise HTTPException(status_code=404, detail="Output file not found")
        
        def iterfile():
            with open(output_file, mode="rb") as file_like:
                yield from file_like
        
        return StreamingResponse(
            iterfile(),
            media_type="video/mp4"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/jobs/recent")
async def get_recent_jobs_endpoint(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None
):
    """최근 작업 목록 조회"""
    try:
        jobs = get_recent_jobs(limit)
        
        # 상태 필터링
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        
        return jobs
    except Exception as e:
        logger.error(f"Error getting recent jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/jobs/search")
async def search_jobs_endpoint(
    query: str,
    limit: int = Query(50, ge=1, le=200)
):
    """작업 검색"""
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Search query required")
        
        jobs = search_jobs(query, limit)
        return jobs
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))