"""
Download Routes
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import logging
from pathlib import Path
from typing import Optional

from api.models import JobStatus
from api.utils import job_status
from api.config import OUTPUT_DIR

# Import database functions from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from database import get_job_by_id

router = APIRouter(prefix="/api", tags=["Download"])
logger = logging.getLogger(__name__)


@router.get("/download/{job_id}",
            summary="클립 다운로드")
async def download_clip(job_id: str):
    """생성된 클립을 다운로드합니다."""
    # Check memory first (current worker)
    output_file = None
    status = None
    
    if job_id in job_status:
        status = job_status[job_id]["status"]
        output_file = job_status[job_id].get("output_file")
        
    # If not found in memory, check database
    if not output_file:
        try:
            db_job = get_job_by_id(job_id)
            if db_job:
                status = db_job.get('status')
                output_file = db_job.get('output_file')
        except Exception as e:
            logger.warning(f"Database lookup failed for job {job_id}: {e}")
    
    if not output_file:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"작업이 완료되지 않았습니다. (현재 상태: {status})")
    
    file_path = Path(output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")
    
    return FileResponse(file_path, media_type='video/mp4', filename=file_path.name)


@router.get("/download/{job_id}/individual/{index}",
            summary="개별 클립 다운로드")
async def download_individual_clip(job_id: str, index: int):
    """개별 클립을 다운로드합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    individual_clips = job_status[job_id].get("individual_clips", [])
    if not individual_clips or index >= len(individual_clips):
        raise HTTPException(status_code=404, detail="Individual clip not found")
    
    clip_path = Path(individual_clips[index])
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail=f"Clip file not found: {clip_path}")
    
    return FileResponse(clip_path, media_type='video/mp4', filename=clip_path.name)


@router.get("/download/batch/{job_id}",
            summary="배치 결과 다운로드")
async def download_batch_results(job_id: str):
    """배치 작업의 모든 결과를 ZIP 파일로 다운로드합니다."""
    import zipfile
    import io
    
    # Get job status
    if job_id not in job_status:
        # Try database
        try:
            db_job = get_job_by_id(job_id)
            if not db_job:
                raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
            
            output_files = db_job.get('output_files', [])
            status = db_job.get('status')
        except Exception as e:
            logger.warning(f"Database lookup failed for job {job_id}: {e}")
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    else:
        output_files = job_status[job_id].get("output_files", [])
        status = job_status[job_id]["status"]
    
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"작업이 완료되지 않았습니다. (현재 상태: {status})")
    
    if not output_files:
        raise HTTPException(status_code=404, detail="출력 파일이 없습니다.")
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_info in output_files:
            file_path = Path(OUTPUT_DIR.parent) / file_info["file"]
            if file_path.exists():
                # Add file to ZIP with a descriptive name
                clip_number = file_info.get("clip_number", 0)
                if clip_number == 999:  # Batch file
                    arcname = f"batch_result.mp4"
                elif clip_number == 0:  # Preview/review clip
                    arcname = f"00_study_clip.mp4"
                else:
                    arcname = f"{clip_number:02d}_{file_path.stem}.mp4"
                
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    
    # Return ZIP file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=batch_results_{job_id[:8]}_{timestamp}.zip"
        }
    )