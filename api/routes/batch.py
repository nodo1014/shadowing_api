"""
Batch Clip Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
import logging
import asyncio
from datetime import datetime
from pathlib import Path

from api.models import BatchClippingRequest, ClippingResponse
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import (
    generate_blank_text, 
    update_job_status_both,
    job_status,
    cleanup_memory_jobs,
    active_processes
)

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from ass_generator import ASSGenerator
from video_encoder import VideoEncoder
from template_video_encoder import TemplateVideoEncoder
from review_clip_generator import ReviewClipGenerator
from enhanced_batch_renderer import EnhancedBatchRenderer

router = APIRouter(prefix="/api", tags=["Clipping"])
logger = logging.getLogger(__name__)


@router.post("/clip/batch",
             response_model=ClippingResponse,
             summary="배치 비디오 클립 생성 요청")
async def create_batch_clips(
    request: BatchClippingRequest,
    background_tasks: BackgroundTasks
):
    """
    여러 개의 비디오 클립을 한 번에 생성합니다.
    각 클립은 독립적인 파일로 생성됩니다.
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # Debug logging
    logger.info(f"[Job {job_id}] Batch request - Type: {request.template_number}, Clips: {len(request.clips)}")
    if request.title_1 or request.title_2:
        logger.info(f"[Job {job_id}] Titles - title_1: '{request.title_1}', title_2: '{request.title_2}'")
    else:
        logger.info(f"[Job {job_id}] No titles provided")
    for i, clip in enumerate(request.clips):
        logger.info(f"  Clip {i+1}: Keywords: {clip.keywords}")
    
    # 메모리 정리
    cleanup_memory_jobs()
    
    # 작업 상태 초기화
    job_status[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "배치 작업 대기 중...",
        "output_files": [],
        "total_clips": len(request.clips),
        "completed_clips": 0,
        "error": None
    }
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_batch_clipping,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"배치 클리핑 작업이 시작되었습니다. (총 {len(request.clips)}개)"
    )


async def process_batch_clipping(job_id: str, request: BatchClippingRequest):
    """배치 비디오 클리핑 처리"""
    try:
        # 작업 시작
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "배치 클리핑 준비 중..."
        
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
        
        output_files = []
        review_clip_path = None
        
        # study 모드인 경우 학습 클립을 먼저 생성
        if request.study:
            logger.info(f"[Job {job_id}] Creating study clip FIRST...")
            job_status[job_id]["progress"] = 5
            mode_text = "미리보기" if request.study == "preview" else "복습"
            job_status[job_id]["message"] = f"{mode_text} 클립 생성 중..."
            
            # 클립 데이터 준비
            clips_data_for_review = []
            clip_timestamps = []
            for clip_data in request.clips:
                clips_data_for_review.append({
                    'text_eng': clip_data.text_eng,
                    'text_kor': clip_data.text_kor
                })
                clip_timestamps.append((clip_data.start_time, clip_data.end_time))
            
            # 리뷰 클립 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            review_filename = f"{timestamp}_tp_{request.template_number}_review.mp4"
            review_clip_path = job_dir / review_filename
            
            # 간단한 리뷰 클립 생성
            review_generator = ReviewClipGenerator()
            
            try:
                # 모드에 따른 타이틀 텍스트 결정
                review_title = "스피드 미리보기" if request.study == "preview" else "스피드 복습"
                
                success = await review_generator.create_review_clip(
                    clips_data=clips_data_for_review,
                    output_path=str(review_clip_path),
                    title=review_title,
                    template_number=request.template_number,
                    video_path=request.video_path,
                    clip_timestamps=clip_timestamps
                )
                
                if success and review_clip_path.exists():
                    logger.info(f"Review clip created: {review_clip_path}")
                    # 리뷰 클립을 임시 저장 (나중에 위치에 따라 추가)
                    job_status[job_id]["review_clip_data"] = {
                        "type": "study",
                        "file": str(review_clip_path),
                        "description": f"{review_title} 클립"
                    }
                else:
                    logger.warning("Failed to create review clip, continuing without it")
                    review_clip_path = None
                    
            except Exception as e:
                logger.error(f"Review clip creation error: {e}")
                # 리뷰 클립 실패해도 계속 진행
                review_clip_path = None
        
        ass_generator = ASSGenerator()
        video_encoder = VideoEncoder()
        
        # 각 클립 처리
        for idx, clip_data in enumerate(request.clips):
            clip_num = idx + 1
            job_status[job_id]["progress"] = int((idx / len(request.clips)) * 90)
            job_status[job_id]["message"] = f"클립 {clip_num}/{len(request.clips)} 처리 중..."
            
            # 클립별 디렉토리
            clip_dir = job_dir / f"clip_{clip_num:03d}"
            clip_dir.mkdir(exist_ok=True)
            
            # 텍스트 블랭크 처리 (Type 2, 3인 경우 자동 생성)
            text_eng_blank = None
            if request.template_number in [2, 3]:
                text_eng_blank = generate_blank_text(clip_data.text_eng, clip_data.keywords)
            
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
                            lines.append(word)
                            current_line = []
                            current_length = 0
                    else:
                        current_line.append(word)
                        current_length += word_length
                
                if current_line:
                    lines.append(' '.join(current_line))
                
                return '\\N'.join(lines)
            
            # 타이틀 로깅 추가
            logger.info(f"[Job {job_id}] Clip {clip_num} - title_1: '{request.title_1}', title_2: '{request.title_2}'")
            
            # 자막 데이터
            subtitle_data = {
                'start_time': 0,
                'end_time': clip_data.end_time - clip_data.start_time,
                'english': clip_data.text_eng,
                'korean': clip_data.text_kor,
                'note': clip_data.note,
                'eng': clip_data.text_eng,
                'kor': clip_data.text_kor,
                'eng_text_l': clip_data.text_eng,  # Long version (일반)
                'eng_text_s': add_line_breaks(clip_data.text_eng, 20),  # Short version (쇼츠)
                'kor_text_l': clip_data.text_kor,  # Long version (일반)
                'kor_text_s': add_line_breaks(clip_data.text_kor, 15),  # Short version (쇼츠)
                'keywords': clip_data.keywords,  # Type 2를 위한 키워드
                'template_number': request.template_number,  # 클리핑 타입 전달
                'text_eng_blank': text_eng_blank,  # Type 2를 위한 blank 텍스트
                'title_1': request.title_1,  # 배치 전체 타이틀 첫 번째 줄
                'title_2': request.title_2,  # 배치 전체 타이틀 두 번째 줄
                'title_3': request.title_3   # 배치 전체 타이틀 세 번째 줄 (설명용)
            }
            
            # 비디오 클리핑 - 템플릿 기반 (자막 파일 자동 생성)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_tp_{request.template_number}_c{clip_num:03d}.mp4"
            output_path = clip_dir / filename
            
            # 템플릿 기반 인코더 사용
            template_encoder = TemplateVideoEncoder()
            
            # 템플릿 이름 결정
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
                start_time=clip_data.start_time,
                end_time=clip_data.end_time,
                padding_before=0.5,
                padding_after=0.5
            )
            
            if success:
                output_files.append({
                    "clip_number": clip_num,
                    "file": str(output_path.relative_to(OUTPUT_DIR.parent)),
                    "text_eng": clip_data.text_eng,
                    "text_kor": clip_data.text_kor
                })
                job_status[job_id]["completed_clips"] = clip_num
            else:
                raise Exception(f"클립 {clip_num} 생성 실패")
        
        # study 모드인 경우 preview는 처음에, review는 마지막에 추가
        if review_clip_path and job_status[job_id].get("review_clip_data"):
            review_data = job_status[job_id]["review_clip_data"]
            review_entry = {
                "clip_number": 0 if request.study == "preview" else len(output_files) + 1,
                "file": str(Path(review_data["file"]).relative_to(OUTPUT_DIR.parent)),
                "text_eng": review_data["description"],
                "text_kor": review_data["description"]
            }
            
            if request.study == "preview":
                # preview는 처음에 삽입
                output_files.insert(0, review_entry)
            else:
                # review는 마지막에 추가
                output_files.append(review_entry)
        
        # 배치 렌더링 처리 (쇼츠 템플릿인 경우)
        if request.template_number in [11, 12, 13]:  # 쇼츠 템플릿
            logger.info(f"[Job {job_id}] Starting batch rendering for shorts...")
            job_status[job_id]["progress"] = 92
            job_status[job_id]["message"] = "배치 렌더링 중..."
            
            # 배치 렌더러 사용
            batch_renderer = EnhancedBatchRenderer()
            
            # 배치 출력 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_filename = f"{timestamp}_tp_{request.template_number}_batch.mp4"
            batch_output_path = job_dir / batch_filename
            
            # 개별 비디오 파일 경로 목록
            video_files = []
            for file_info in output_files:
                if file_info["clip_number"] > 0:  # 리뷰 클립은 제외
                    full_path = OUTPUT_DIR.parent / file_info["file"]
                    if full_path.exists():
                        video_files.append(str(full_path))
            
            # 배치 비디오 생성
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                executor,
                batch_renderer.create_batch_video,
                video_files,
                str(batch_output_path),
                request.title_1,
                request.title_2
            )
            
            if success and batch_output_path.exists():
                output_files.append({
                    "clip_number": 999,  # 특별한 번호로 배치 파일 표시
                    "file": str(batch_output_path.relative_to(OUTPUT_DIR.parent)),
                    "text_eng": f"Batch video ({len(video_files)} clips)",
                    "text_kor": f"배치 비디오 ({len(video_files)}개 클립)"
                })
                logger.info(f"Batch video created: {batch_output_path}")
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        job_status[job_id]["message"] = f"배치 클리핑이 완료되었습니다. (총 {len(output_files)}개)"
        job_status[job_id]["output_files"] = output_files
        
        logger.info(f"[Job {job_id}] Batch clipping completed: {len(output_files)} files")
    
    except Exception as e:
        logger.error(f"[Job {job_id}] Batch clipping error: {str(e)}")
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = "배치 클리핑 실패"