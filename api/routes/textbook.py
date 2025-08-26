"""
Textbook Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
import logging
from datetime import datetime
from pathlib import Path
import json

from api.models import TextbookLessonRequest, ClippingResponse
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import update_job_status_both, job_status

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from template_video_encoder import TemplateVideoEncoder
from database import save_job_to_db

router = APIRouter(prefix="/api", tags=["Clipping"])
logger = logging.getLogger(__name__)


@router.post("/clip/textbook",
             response_model=ClippingResponse,
             summary="교재형 학습 비디오 생성")
async def create_textbook_lesson(
    request: TextbookLessonRequest,
    background_tasks: BackgroundTasks
):
    """
    5개의 북마크를 활용하여 영어 교재형 학습 비디오를 생성합니다.
    
    구성:
    - Warmup: 오늘의 표현 소개
    - Expression 학습: 각 표현별 소개, 원본, 분석, 연습
    - Pattern Focus: 공통 패턴 분석
    - Review: 복습 퀴즈
    - Wrap-up: 마무리
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # 북마크된 세그먼트 개수 계산
    bookmarked_count = sum(1 for seg in request.subtitle_segments if seg.is_bookmarked)
    logger.info(f"[Job {job_id}] Textbook lesson request - {bookmarked_count} bookmarks")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "교재형 학습 준비 중...",
        "output_file": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "subtitle_segments": [s.dict() for s in request.subtitle_segments],
        "lesson_title": request.lesson_title
    }
    job_status[job_id] = job_data
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_textbook_lesson,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"교재형 학습 비디오 생성이 시작되었습니다. ({bookmarked_count}개 북마크)"
    )


async def process_textbook_lesson(job_id: str, request: TextbookLessonRequest):
    """교재형 학습 비디오 처리"""
    try:
        # 작업 시작
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "교재형 학습 비디오 생성 중..."
        
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
        
        # 출력 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{timestamp}_tp_{request.template_number}_textbook.mp4"
        output_path = job_dir / output_filename
        
        # 템플릿 이름 결정
        template_name = TEMPLATE_MAPPING.get(request.template_number, "template_91")
        
        # 자막 세그먼트 데이터 준비
        segments = []
        for idx, segment in enumerate(request.subtitle_segments):
            segment_dict = segment.dict()
            # 템플릿 인코더가 기대하는 형식으로 변환
            segment_dict['english_text'] = segment_dict.get('text_eng', '')
            segment_dict['korean_text'] = segment_dict.get('text_kor', '')
            segment_dict['start_time'] = segment_dict.get('start_time', 0)
            segment_dict['duration'] = segment_dict.get('end_time', 0) - segment_dict.get('start_time', 0)
            # is_bookmarked는 그대로 유지
            segments.append(segment_dict)
            
        # 북마크 확인 로그
        bookmarked_count = sum(1 for seg in segments if seg.get('is_bookmarked', False))
        logger.info(f"[Job {job_id}] Processing {len(segments)} segments, {bookmarked_count} bookmarked")
        
        # 디버그: 세그먼트 내용 확인
        for i, seg in enumerate(segments[:3]):  # 처음 3개만
            logger.info(f"Segment {i}: is_bookmarked={seg.get('is_bookmarked')}, text_eng={seg.get('text_eng', '')[:30]}...")
        
        # 진행 상황 업데이트
        job_status[job_id]["progress"] = 20
        job_status[job_id]["message"] = "템플릿 비디오 인코더 초기화..."
        
        # 템플릿 비디오 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # apply_template 메서드 호출
        success = template_encoder.apply_template(
            video_path=str(media_path),
            output_path=str(output_path),
            template_name=template_name,
            segments=segments
        )
        
        if not success:
            raise Exception("Failed to create textbook lesson video")
        
        # 출력 파일 크기 확인
        if output_path.exists():
            file_size = output_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
        else:
            raise Exception("Output file not created")
        
        # 메타데이터 저장
        metadata = {
            "job_id": job_id,
            "media_path": str(media_path),
            "template_number": request.template_number,
            "lesson_title": request.lesson_title,
            "subtitle_segments": segments,
            "output_file": str(output_path),
            "file_size_mb": file_size_mb,
            "created_at": datetime.now().isoformat()
        }
        
        with open(job_dir / "textbook_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        # 북마크된 세그먼트 개수 계산
        bookmarked_count = sum(1 for seg in request.subtitle_segments if seg.is_bookmarked)
        job_status[job_id]["message"] = f"교재형 학습 비디오 생성 완료! ({bookmarked_count}개 북마크)"
        job_status[job_id]["output_file"] = str(output_path)
        job_status[job_id]["file_size_mb"] = file_size_mb
        
        # DB에 저장
        job_data_for_db = {
            "status": "completed",
            "progress": 100,
            "media_path": str(media_path),
            "template_number": request.template_number,
            "start_time": request.subtitle_segments[0].start_time if request.subtitle_segments else 0,
            "end_time": request.subtitle_segments[-1].end_time if request.subtitle_segments else 0,
            "output_file": str(output_path),
            "output_size": file_size,
            "text_eng": request.lesson_title,
            "text_kor": f"{bookmarked_count}개 북마크",
            "note": json.dumps({"lesson_title": request.lesson_title}),
            "keywords": []
        }
        save_job_to_db(job_id, job_data_for_db)
        
    except Exception as e:
        logger.error(f"Error creating textbook lesson: {e}", exc_info=True)
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"교재형 학습 비디오 생성 오류: {str(e)}"
        
        # DB에 실패 상태 저장
        job_data_for_db = {
            "status": "failed",
            "progress": 0,
            "media_path": request.media_path,
            "template_number": request.template_number,
            "start_time": 0,
            "end_time": 0,
            "error_message": str(e)
        }
        save_job_to_db(job_id, job_data_for_db)