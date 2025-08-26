"""
Extract Range Routes - 구간 추출 (원본 스타일)
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
import uuid
import logging
from datetime import datetime
from pathlib import Path
import json

from api.models import ExtractRangeRequest, SubtitleInfo, ClippingResponse
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import update_job_status_both, job_status

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from template_video_encoder import TemplateVideoEncoder
from ass_generator import ASSGenerator

router = APIRouter(prefix="/api", tags=["Extract"])
logger = logging.getLogger(__name__)


@router.post("/extract/range",
             response_model=ClippingResponse,
             summary="구간 추출 (원본 스타일)")
async def extract_range(
    request: ExtractRangeRequest,
    background_tasks: BackgroundTasks
):
    """
    지정된 구간을 추출하여 여러 자막을 포함한 하나의 클립을 생성합니다.
    
    - 문장 단위 분할 없음
    - 자막은 원본 타이밍에 렌더링
    - 스타일은 통일된 형식 적용
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # Debug logging
    logger.info(f"[Job {job_id}] Range extraction request")
    logger.info(f"  Range: {request.start_time}-{request.end_time}s")
    logger.info(f"  Subtitles: {len(request.subtitles)} items")
    logger.info(f"  Template: {request.template_number}")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "구간 추출 대기 중...",
        "output_file": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "subtitle_count": len(request.subtitles)
    }
    job_status[job_id] = job_data
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_range_extraction,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"구간 추출 작업이 시작되었습니다. ({request.end_time - request.start_time:.1f}초)"
    )


async def process_range_extraction(job_id: str, request: ExtractRangeRequest):
    """구간 추출 처리"""
    try:
        # 작업 시작
        update_job_status_both(job_id, "processing", 10, message="구간 추출 준비 중...")
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 날짜별 디렉토리 구조
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 자막 파일 생성
        update_job_status_both(job_id, "processing", 20, message="자막 파일 생성 중...")
        
        ass_path = job_dir / "subtitles.ass"
        create_multi_subtitle_file(ass_path, request.subtitles, request.start_time)
        
        # 자막 데이터 준비 (템플릿 인코더용)
        # 전체 구간을 하나의 subtitle_data로 처리
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'subtitles': request.subtitles,  # 여러 자막 정보 전달
            'ass_file': str(ass_path),  # 생성된 ASS 파일 경로
            'template_number': request.template_number,
            'title_1': request.title_1,
            'title_2': request.title_2
        }
        
        # 비디오 추출
        update_job_status_both(job_id, "processing", 50, message="비디오 추출 중...")
        
        # 템플릿 기반 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        duration = int(request.end_time - request.start_time)
        filename = f"{timestamp}_extract_{duration}s.mp4"
        output_path = job_dir / filename
        
        # 템플릿 이름
        template_name = TEMPLATE_MAPPING.get(request.template_number, "template_original")
        
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
            save_individual_clips=False
        )
        
        if success and output_path.exists():
            update_job_status_both(job_id, "processing", 90, message="추출 완료, 파일 정리 중...")
            
            # 파일 크기 계산
            file_size = output_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # 메타데이터 저장
            metadata = {
                "job_id": job_id,
                "media_path": str(media_path),
                "template_number": request.template_number,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "duration": request.end_time - request.start_time,
                "subtitle_count": len(request.subtitles),
                "subtitles": [s.dict() for s in request.subtitles],
                "output_file": str(output_path),
                "file_size_mb": file_size_mb,
                "created_at": datetime.now().isoformat()
            }
            
            with open(job_dir / "extraction_metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 작업 완료
            update_job_status_both(
                job_id,
                "completed",
                100,
                message="구간 추출이 완료되었습니다.",
                output_file=str(output_path)
            )
            
            logger.info(f"[Job {job_id}] Range extraction completed: {output_path}")
            
        else:
            raise Exception("비디오 추출 실패")
    
    except Exception as e:
        logger.error(f"[Job {job_id}] Extraction error: {str(e)}")
        update_job_status_both(
            job_id,
            "failed",
            0,
            message="구간 추출 실패",
            error_message=str(e)
        )


def create_multi_subtitle_file(ass_path: Path, subtitles: List[SubtitleInfo], offset: float):
    """여러 자막이 포함된 ASS 파일 생성"""
    
    # ASS 헤더
    ass_content = """[Script Info]
Title: Multi-line Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,나눔고딕,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,20,1
Style: Korean,나눔고딕,28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # 각 자막을 ASS 이벤트로 변환
    for subtitle in subtitles:
        # 오프셋을 적용한 시간 (구간 시작을 0으로)
        start_time = subtitle.start - offset
        end_time = subtitle.end - offset
        
        # 시간 포맷 변환 (초 -> HH:MM:SS.CC)
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}:{minutes:02d}:{secs:05.2f}"
        
        start_str = format_time(start_time)
        end_str = format_time(end_time)
        
        # 영어 자막
        if subtitle.eng:
            ass_content += f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{subtitle.eng}\n"
        
        # 한글 자막
        if subtitle.kor:
            ass_content += f"Dialogue: 0,{start_str},{end_str},Korean,,0,0,0,,{subtitle.kor}\n"
    
    # 파일 저장
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    logger.info(f"Created multi-subtitle file: {ass_path} with {len(subtitles)} subtitles")