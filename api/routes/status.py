"""
Job Status Routes
"""
from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime
from pathlib import Path

from api.models import JobStatus
from api.utils import get_job_status as get_job_status_util
from api.config import OUTPUT_DIR

# Import database functions from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from database import get_job_by_id

router = APIRouter(prefix="/api", tags=["Status"])
logger = logging.getLogger(__name__)


@router.get("/status/{job_id}", 
            response_model=JobStatus,
            summary="작업 상태 확인")
async def get_job_status(job_id: str):
    """작업 상태를 확인합니다."""
    # Get status from memory or Redis
    status_data = get_job_status_util(job_id)
    
    if status_data:
        # job_id가 이미 status_data에 있으면 제거
        if 'job_id' in status_data:
            status_data.pop('job_id')
        
        # output_files 확인을 위한 로그
        logger.info(f"Status data for job {job_id}: output_files={status_data.get('output_files', 'NOT FOUND')}")
        
        return JobStatus(
            job_id=job_id,
            **status_data
        )
    
    # If not in memory/Redis, check database
    try:
        db_job = get_job_by_id(job_id)
        if db_job:
            return JobStatus(
                job_id=job_id,
                status=db_job.get('status', 'unknown'),
                progress=db_job.get('progress', 0),
                message=db_job.get('message', ''),
                output_file=db_job.get('output_file'),
                output_files=db_job.get('output_files', []),
                error=db_job.get('error'),
                created_at=db_job.get('created_at'),
                updated_at=db_job.get('updated_at')
            )
    except Exception as e:
        logger.warning(f"Database lookup failed for job {job_id}: {e}")
    
    # Job not found anywhere
    raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")