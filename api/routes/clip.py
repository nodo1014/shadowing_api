"""
Single Clip Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
import logging
from datetime import datetime
from pathlib import Path

from api.models import ClippingRequest, ClippingResponse
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor
from api.utils import (
    generate_blank_text, 
    update_job_status_both,
    job_status,
    active_processes
)

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from template_video_encoder import TemplateVideoEncoder
from database import save_job_to_db

router = APIRouter(prefix="/api", tags=["Clipping"])
logger = logging.getLogger(__name__)


@router.post("/clip", 
             response_model=ClippingResponse,
             summary="비디오 클립 생성 요청")
async def create_clip(
    request: ClippingRequest,
    background_tasks: BackgroundTasks
):
    """
    비디오 클립을 생성합니다.
    
    - **media_path**: 원본 비디오 파일 경로
    - **start_time**: 클립 시작 시간 (초)
    - **end_time**: 클립 종료 시간 (초)
    - **text_eng**: 영문 자막
    - **text_kor**: 한국어 자막
    - **note**: 설명 (선택)
    - **keywords**: 키워드 리스트 (선택)
    - **template_number**: 1 (기본), 2 (키워드 블랭크), 또는 3 (점진적 학습)
    - **individual_clips**: 개별 클립 저장 여부
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # Debug logging
    logger.info(f"[Job {job_id}] Single clip request - Type: {request.template_number}, Keywords: {request.keywords}")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "작업 대기 중...",
        "output_file": None,
        "individual_clips": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "text_eng": request.text_eng,
        "text_kor": request.text_kor,
        "note": request.note,
        "keywords": request.keywords
    }
    job_status[job_id] = job_data
    
    # DB에 저장
    try:
        save_job_to_db(job_id, job_data)
    except Exception as e:
        logger.error(f"Failed to save job to DB: {e}")
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_clipping,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message="클리핑 작업이 시작되었습니다."
    )


async def process_clipping(job_id: str, request: ClippingRequest):
    """비디오 클리핑 처리"""
    
    
    try:
        # 작업 시작 (메모리와 DB 동시 업데이트)
        update_job_status_both(job_id, "processing", 10, message="클리핑 준비 중...")
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 날짜별 디렉토리 구조: /output/YYYY-MM-DD/job_id
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 텍스트 블랭크 처리 (Type 2, 3인 경우 자동 생성)
        text_eng_blank = None
        if request.template_number in [2, 3]:
            text_eng_blank = generate_blank_text(request.text_eng, request.keywords)
        
        # 쇼츠용 줄바꿈 처리 함수
        def add_line_breaks(text: str, max_chars: int = 20) -> str:
            """긴 텍스트에 줄바꿈 추가"""
            if not text or len(text) <= max_chars:
                return text
            
            words = text.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word)
                if current_length + word_length + len(current_line) > max_chars:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = word_length
                else:
                    current_line.append(word)
                    current_length += word_length
            
            if current_line:
                lines.append(' '.join(current_line))
            
            return '\\n'.join(lines)
        
        # 자막 데이터 준비
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'english': request.text_eng,
            'korean': request.text_kor,
            'note': request.note,
            'eng': request.text_eng,  # 호환성
            'kor': request.text_kor,   # 호환성
            'eng_text_l': request.text_eng,  # Long version (일반)
            'eng_text_s': add_line_breaks(request.text_eng, 20),  # Short version (쇼츠)
            'kor_text_l': request.text_kor,  # Long version (일반)
            'kor_text_s': add_line_breaks(request.text_kor, 15),  # Short version (쇼츠)
            'keywords': request.keywords,  # Type 2를 위한 키워드
            'template_number': request.template_number,  # 클리핑 타입 전달
            'text_eng_blank': text_eng_blank  # Type 2를 위한 blank 텍스트
        }
        
        # 자막 파일 생성은 템플릿 인코더가 자동으로 처리
        update_job_status_both(job_id, "processing", 30, message="자막 파일 생성 중...")
        
        # 비디오 클리핑 - 템플릿 기반 접근
        update_job_status_both(job_id, "processing", 50, message="비디오 클리핑 중...")
        
        # 템플릿 기반 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # 날짜시간_tp_X.mp4 형식의 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_tp_{request.template_number}.mp4"
        output_path = job_dir / filename
        
        # 템플릿 이름 결정 (11, 12, 13은 쇼츠 버전으로 매핑)
        from api.config import TEMPLATE_MAPPING
        
        if request.template_number in TEMPLATE_MAPPING:
            template_name = TEMPLATE_MAPPING[request.template_number]
        else:
            template_name = f"template_{request.template_number}"
        
        # 템플릿을 사용하여 비디오 생성
        success = template_encoder.create_from_template(
            template_name=template_name,
            media_path=str(media_path),
            subtitle_data=subtitle_data,
            output_path=str(output_path),
            start_time=request.start_time,
            end_time=request.end_time,
            padding_before=0.5,
            padding_after=0.5,
            save_individual_clips=request.individual_clips
        )
        
        if success:
            update_job_status_both(job_id, "processing", 90, message="클리핑 완료, 파일 정리 중...")
            
            # 개별 클립 찾기
            individual_clips = None
            if request.individual_clips:
                clips_dir = job_dir / "individual_clips"
                if clips_dir.exists():
                    clips = list(clips_dir.glob("*.mp4"))
                    if clips:
                        individual_clips = [str(clip.relative_to(OUTPUT_DIR.parent)) for clip in clips]
            
            # 작업 완료
            update_job_status_both(
                job_id, 
                "completed", 
                100,
                message="클리핑이 완료되었습니다.",
                output_file=str(output_path)
            )
            
            logger.info(f"[Job {job_id}] Clipping completed successfully: {output_path}")
            
        else:
            raise Exception("비디오 생성 실패")
    
    except Exception as e:
        logger.error(f"[Job {job_id}] Error: {str(e)}")
        update_job_status_both(
            job_id,
            "failed",
            0,
            message="클리핑 실패",
            error_message=str(e)
        )


