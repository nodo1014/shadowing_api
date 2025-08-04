"""
Video clipping routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
import logging
import sys

# Import from adapters for backward compatibility
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from database_adapter import save_job_to_db, update_job_status
from video_encoder_adapter import TemplateVideoEncoder, VideoEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["clips"])


class ClipRequest(BaseModel):
    """단일 클립 생성 요청"""
    media_path: str = Field(..., description="원본 미디어 파일 경로")
    start_time: float = Field(..., ge=0, description="시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="종료 시간 (초)")
    text_eng: str = Field(..., min_length=1, description="영문 자막")
    text_kor: str = Field(..., min_length=1, description="한국어 번역")
    note: Optional[str] = Field(None, description="문장 설명")
    keywords: Optional[List[str]] = Field(default_factory=list, description="키워드 목록")
    clipping_type: int = Field(1, ge=1, le=2, description="클리핑 타입")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    template_number: Optional[int] = Field(None, ge=1, le=3, description="템플릿 번호")
    
    @validator('end_time')
    def validate_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v
    
    @validator('media_path')
    def validate_media_path(cls, v):
        if not Path(v).exists():
            raise ValueError(f'Media file not found: {v}')
        return v


class BatchClipRequest(BaseModel):
    """배치 클립 생성 요청"""
    media_path: str = Field(..., description="원본 미디어 파일 경로")
    clips: List[Dict[str, Any]] = Field(..., min_items=1, description="클립 목록")
    clipping_type: int = Field(1, ge=1, le=2, description="클리핑 타입")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    template_number: Optional[int] = Field(None, ge=1, le=3, description="템플릿 번호")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        if not Path(v).exists():
            raise ValueError(f'Media file not found: {v}')
        return v
    
    @validator('clips')
    def validate_clips(cls, v):
        for i, clip in enumerate(v):
            if 'start_time' not in clip or 'end_time' not in clip:
                raise ValueError(f'Clip {i+1}: start_time and end_time are required')
            if 'text_eng' not in clip or 'text_kor' not in clip:
                raise ValueError(f'Clip {i+1}: text_eng and text_kor are required')
            if clip['end_time'] <= clip['start_time']:
                raise ValueError(f'Clip {i+1}: end_time must be greater than start_time')
        return v


async def process_single_clip(job_id: str, request: ClipRequest):
    """단일 클립 처리 백그라운드 작업"""
    try:
        update_job_status(job_id, "processing", progress=10, message="작업 시작")
        
        # 출력 경로 생성
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if request.template_number:
            output_filename = f"{timestamp}_tp_{request.template_number}.mp4"
        else:
            output_filename = f"{timestamp}_type{request.clipping_type}.mp4"
        
        output_dir = Path("./output") / datetime.now().strftime("%Y-%m-%d") / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename
        
        update_job_status(job_id, "processing", progress=30, message="비디오 인코딩 중")
        
        # 처리 로직
        if request.template_number:
            encoder = TemplateVideoEncoder()
            subtitle_data = {
                "text_eng": request.text_eng,
                "text_kor": request.text_kor,
                "note": request.note,
                "keywords": request.keywords
            }
            
            success = encoder.create_from_template(
                template_name=f"template_{request.template_number}",
                media_path=request.media_path,
                subtitle_data=subtitle_data,
                output_path=str(output_path),
                start_time=request.start_time,
                end_time=request.end_time,
                save_individual_clips=request.individual_clips
            )
        else:
            # 기존 Type 1/2 처리
            encoder = VideoEncoder()
            if request.clipping_type == 1:
                encoder.set_pattern(1, 0, 3)
            else:
                encoder.set_pattern(2, 2, 2)
            
            success = encoder.create_shadowing_video(
                media_path=request.media_path,
                ass_path="temp.ass",  # 임시
                output_path=str(output_path),
                start_time=request.start_time,
                end_time=request.end_time,
                save_individual_clips=request.individual_clips
            )
        
        if success:
            update_job_status(
                job_id, "completed",
                progress=100,
                message="작업 완료",
                output_file=str(output_path)
            )
        else:
            raise Exception("비디오 생성 실패")
            
    except Exception as e:
        logger.error(f"Error processing clip: {e}")
        update_job_status(
            job_id, "failed",
            progress=0,
            message=f"작업 실패: {str(e)}",
            error=str(e)
        )


@router.post("/clip/create")
async def create_clip(request: ClipRequest, background_tasks: BackgroundTasks):
    """단일 클립 생성"""
    try:
        job_id = str(uuid.uuid4())
        
        # DB에 작업 저장
        job_data = {
            "id": job_id,
            "type": "single_clip",
            "status": "pending",
            "media_path": request.media_path,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "text_eng": request.text_eng,
            "text_kor": request.text_kor,
            "note": request.note,
            "keywords": request.keywords,
            "clipping_type": request.clipping_type,
            "template_number": request.template_number,
            "individual_clips": request.individual_clips
        }
        save_job_to_db(job_data)
        
        # 백그라운드 작업 시작
        background_tasks.add_task(process_single_clip, job_id, request)
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "클립 생성 작업이 시작되었습니다"
        }
        
    except Exception as e:
        logger.error(f"Error creating clip: {e}")
        raise HTTPException(status_code=400, detail=str(e))