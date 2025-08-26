"""
Admin Routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging
from pathlib import Path

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from database import (
    get_statistics, get_recent_jobs, search_jobs, get_job_by_id,
    delete_job, delete_jobs_bulk, cleanup_old_jobs
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


@router.get("/statistics",
            summary="통계 정보 조회")
async def get_admin_statistics():
    """클리핑 작업 통계 정보를 조회합니다."""
    return get_statistics()


@router.get("/jobs/recent",
            summary="최근 작업 목록 조회")
async def get_recent_jobs_api(limit: int = 50):
    """최근 생성된 작업 목록을 조회합니다."""
    jobs = get_recent_jobs(limit)
    
    # 작업 상태별 카운트
    status_counts = {
        "completed": 0,
        "processing": 0,
        "failed": 0,
        "pending": 0
    }
    
    for job in jobs:
        status = job.get("status", "unknown")
        if status in status_counts:
            status_counts[status] += 1
    
    return {
        "total": len(jobs),
        "status_counts": status_counts,
        "jobs": jobs
    }


@router.get("/jobs/search",
            summary="작업 검색")
async def search_jobs_api(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    template_number: Optional[int] = None
):
    """작업을 검색합니다."""
    jobs = search_jobs(
        keyword=keyword,
        status=status,
        start_date=start_date,
        end_date=end_date,
        template_number=template_number
    )
    
    # 작업 상태별 카운트
    status_counts = {
        "completed": 0,
        "processing": 0,
        "failed": 0,
        "pending": 0
    }
    
    for job in jobs:
        s = job.get("status", "unknown")
        if s in status_counts:
            status_counts[s] += 1
    
    return {
        "total": len(jobs),
        "status_counts": status_counts,
        "jobs": jobs
    }


@router.post("/cleanup",
             summary="고아 레코드 정리")
async def cleanup_orphaned_records():
    """파일이 없는 DB 레코드를 정리합니다."""
    try:
        cleaned_count = 0
        jobs = get_recent_jobs(1000)  # 최근 1000개 작업 확인
        
        for job in jobs:
            if job.get('status') == 'completed' and job.get('output_file'):
                output_path = Path(job['output_file'])
                if not output_path.exists():
                    # 파일이 없는 경우 DB에서 제거
                    try:
                        delete_job(job['job_id'], delete_file=False)
                        cleaned_count += 1
                        logger.info(f"Orphaned record cleaned: {job['job_id']}")
                    except Exception as e:
                        logger.error(f"Failed to clean orphaned record {job['job_id']}: {e}")
        
        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "message": f"{cleaned_count}개의 고아 레코드가 정리되었습니다."
        }
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}",
            summary="작업 상세 조회")
async def get_job_detail_api(job_id: str):
    """특정 작업의 상세 정보를 조회합니다."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    # 파일 존재 여부 확인
    if job.get('output_file'):
        output_path = Path(job['output_file'])
        job['file_exists'] = output_path.exists()
        if output_path.exists():
            job['file_size_mb'] = round(output_path.stat().st_size / (1024 * 1024), 2)
    
    # output_files가 있는 경우 (배치 작업)
    if job.get('output_files'):
        for file_info in job['output_files']:
            if file_info.get('file'):
                file_path = Path(file_info['file'])
                file_info['exists'] = file_path.exists()
    
    return job


@router.delete("/jobs",
               summary="작업 일괄 삭제")
async def delete_jobs_api(
    job_ids: List[str],
    delete_files: bool = True
):
    """여러 작업을 일괄 삭제합니다."""
    results = delete_jobs_bulk(job_ids, delete_files)
    
    return {
        "total": len(job_ids),
        "deleted": results["deleted"],
        "failed": results["failed"],
        "errors": results["errors"]
    }


@router.post("/cleanup/old",
             summary="오래된 작업 정리")
async def cleanup_old_jobs_api(
    days_old: int = 30,
    delete_files: bool = True
):
    """지정된 일수보다 오래된 작업을 정리합니다."""
    count = cleanup_old_jobs(days_old, delete_files)
    
    return {
        "success": True,
        "deleted_count": count,
        "message": f"{count}개의 오래된 작업이 정리되었습니다."
    }