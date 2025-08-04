"""
Batch processing routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Dict, Any
from pathlib import Path
import uuid
import json
import tempfile
import subprocess
import logging
import sys

# Import from adapter
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from database_adapter import save_job_to_db, update_job_status, get_job_by_id
from shadowing_maker.api.routes.clip import BatchClipRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batch", tags=["batch"])


async def process_batch_clips(job_id: str, request: BatchClipRequest):
    """배치 클립 처리"""
    try:
        update_job_status(job_id, "processing", progress=5, message="배치 작업 시작")
        
        from datetime import datetime
        batch_dir = Path("./output") / datetime.now().strftime("%Y-%m-%d") / job_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        temp_clips = []
        total_clips = len(request.clips)
        
        # 각 클립 처리
        for i, clip_data in enumerate(request.clips):
            clip_progress = int((i / total_clips) * 80) + 10
            update_job_status(
                job_id, "processing",
                progress=clip_progress,
                message=f"클립 {i+1}/{total_clips} 처리 중"
            )
            
            # 개별 클립 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_id = f"{job_id}_{i+1:04d}"
            
            if request.template_number:
                clip_filename = f"{timestamp}_tp_{request.template_number}_{i+1:04d}.mp4"
            else:
                clip_filename = f"{timestamp}_type{request.clipping_type}_{i+1:04d}.mp4"
            
            clip_path = batch_dir / clip_filename
            
            # 템플릿 또는 타입별 처리
            if request.template_number:
                from video_encoder_adapter import TemplateVideoEncoder
                encoder = TemplateVideoEncoder()
                subtitle_data = {
                    "text_eng": clip_data["text_eng"],
                    "text_kor": clip_data["text_kor"],
                    "note": clip_data.get("note", ""),
                    "keywords": clip_data.get("keywords", [])
                }
                
                success = encoder.create_from_template(
                    template_name=f"template_{request.template_number}",
                    media_path=request.media_path,
                    subtitle_data=subtitle_data,
                    output_path=str(clip_path),
                    start_time=clip_data["start_time"],
                    end_time=clip_data["end_time"],
                    save_individual_clips=request.individual_clips
                )
            else:
                from video_encoder_adapter import VideoEncoder
                encoder = VideoEncoder()
                if request.clipping_type == 1:
                    encoder.set_pattern(1, 0, 3)
                else:
                    encoder.set_pattern(2, 2, 2)
                
                success = encoder.create_shadowing_video(
                    media_path=request.media_path,
                    ass_path="temp.ass",
                    output_path=str(clip_path),
                    start_time=clip_data["start_time"],
                    end_time=clip_data["end_time"],
                    save_individual_clips=request.individual_clips
                )
            
            if success:
                temp_clips.append(str(clip_path))
                results.append({
                    "clip_id": clip_id,
                    "filename": clip_filename,
                    "status": "completed",
                    "path": str(clip_path)
                })
            else:
                results.append({
                    "clip_id": clip_id,
                    "status": "failed",
                    "error": "Failed to create clip"
                })
        
        # 통합 비디오 생성
        if temp_clips and len(temp_clips) > 1:
            update_job_status(
                job_id, "processing",
                progress=90,
                message="통합 비디오 생성 중"
            )
            
            combined_filename = f"combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            combined_path = batch_dir / combined_filename
            
            # FFmpeg concat을 사용한 비디오 병합
            concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            for clip_path in temp_clips:
                escaped_path = clip_path.replace('\\', '/').replace("'", "'\\''")
                concat_file.write(f"file '{escaped_path}'\n")
            concat_file.close()
            
            concat_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c', 'copy',
                str(combined_path)
            ]
            
            result = subprocess.run(concat_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                results.append({
                    "clip_id": "combined",
                    "filename": combined_filename,
                    "status": "completed",
                    "path": str(combined_path),
                    "is_combined": True
                })
            
            # 임시 파일 삭제
            Path(concat_file.name).unlink(missing_ok=True)
        
        # 결과 저장
        results_file = batch_dir / "results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        update_job_status(
            job_id, "completed",
            progress=100,
            message="배치 작업 완료",
            output_file=str(batch_dir),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        update_job_status(
            job_id, "failed",
            progress=0,
            message=f"배치 작업 실패: {str(e)}",
            error=str(e)
        )


@router.post("/create")
async def create_batch_clips(request: BatchClipRequest, background_tasks: BackgroundTasks):
    """배치 클립 생성"""
    try:
        job_id = str(uuid.uuid4())
        
        # DB에 작업 저장
        job_data = {
            "id": job_id,
            "type": "batch_clip",
            "status": "pending",
            "media_path": request.media_path,
            "clips": request.clips,
            "clipping_type": request.clipping_type,
            "template_number": request.template_number,
            "individual_clips": request.individual_clips,
            "total_clips": len(request.clips)
        }
        save_job_to_db(job_data)
        
        # 백그라운드 작업 시작
        background_tasks.add_task(process_batch_clips, job_id, request)
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"{len(request.clips)}개 클립 생성 작업이 시작되었습니다",
            "total_clips": len(request.clips)
        }
        
    except Exception as e:
        logger.error(f"Error creating batch clips: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_id}")
async def get_batch_status(job_id: str):
    """배치 작업 상태 조회"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data.get("type") != "batch_clip":
            raise HTTPException(status_code=400, detail="Not a batch job")
        
        return {
            "id": job_data["id"],
            "status": job_data["status"],
            "progress": job_data.get("progress", 0),
            "message": job_data.get("message", ""),
            "total_clips": job_data.get("total_clips", 0),
            "results": job_data.get("results", []),
            "created_at": job_data.get("created_at"),
            "completed_at": job_data.get("completed_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{job_id}/{clip_type}")
async def download_batch_result(job_id: str, clip_type: str):
    """배치 결과 다운로드"""
    try:
        job_data = get_job_by_id(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        batch_dir = Path(job_data.get("output_file", ""))
        
        if clip_type == "combined":
            # 통합 비디오 찾기
            combined_files = list(batch_dir.glob("combined_*.mp4"))
            if not combined_files:
                raise HTTPException(status_code=404, detail="Combined video not found")
            return FileResponse(
                path=str(combined_files[0]),
                media_type="video/mp4",
                filename=combined_files[0].name
            )
        else:
            # 개별 클립 또는 전체 압축 파일
            raise HTTPException(status_code=400, detail="Not implemented yet")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading batch result: {e}")
        raise HTTPException(status_code=500, detail=str(e))