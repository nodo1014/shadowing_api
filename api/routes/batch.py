import asyncio
import json
import logging
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, validator

# Update imports to use proper paths
from api.models import BatchClippingRequest, ClippingResponse, ClipData
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import (
    generate_blank_text, 
    update_job_status_both
)
from api.utils.id_generator import get_next_folder_id
from api.db_utils import (
    get_client_info
)

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from video_encoder import VideoEncoder
from template_video_encoder import TemplateVideoEncoder
from review_clip_generator import ReviewClipGenerator
from enhanced_batch_renderer import EnhancedBatchRenderer
# DB imports 비활성화

router = APIRouter(prefix="/api", tags=["Clipping"])
logger = logging.getLogger(__name__)


class MultimediaBatchRequest(BaseModel):
    """다중 미디어 배치 요청 모델"""
    clips: List[ClipData] = Field(..., description="각 클립에 media_path가 포함된 클립 데이터 리스트")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    title_1: Optional[str] = Field(None, description="타이틀 첫 번째 줄")
    title_2: Optional[str] = Field(None, description="타이틀 두 번째 줄")
    title_3: Optional[str] = Field(None, description="타이틀 세 번째 줄")
    study: Optional[str] = Field(None, description="학습 모드")
    
    @validator('clips')
    def validate_clips_have_media(cls, v):
        for i, clip in enumerate(v):
            if not clip.media_path:
                raise ValueError(f'클립 {i+1}에 media_path가 지정되지 않았습니다.')
        return v


@router.post("/clip/batch",
             response_model=ClippingResponse,
             summary="배치 비디오 클립 생성 요청")
async def create_batch_clips(
    request: BatchClippingRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    여러 개의 비디오 클립을 한 번에 생성합니다.
    각 클립은 독립적인 파일로 생성됩니다.
    """
    # Job ID는 여전히 UUID 사용 (DB 키로 사용)
    job_id = str(uuid.uuid4())
    
    # 폴더명은 날짜별 순차 번호 사용
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder_id = get_next_folder_id(date_str)
    
    # API 요청 로깅
    request_start_time = time.time()
    client_info = get_client_info(req)
    logger.info(f"[Job {job_id}] Batch request - Type: {request.template_number}, Clips: {len(request.clips)}")
    
    # 타이틀 정보 로깅
    if not request.title_1 and not request.title_2:
        logger.info(f"[Job {job_id}] No titles provided")
    else:
        logger.info(f"[Job {job_id}] Title 1: {request.title_1}, Title 2: {request.title_2}")
    
    # 각 클립의 키워드 로깅
    for i, clip in enumerate(request.clips, 1):
        logger.info(f"  Clip {i}: Keywords: {clip.keywords}")
    
    # 메모리 상태 저장
    from api.utils.job_management import job_status
    job_data = {
        "job_id": job_id,
        "status": "accepted", 
        "progress": 0,
        "message": f"배치 클리핑 작업이 시작되었습니다. (총 {len(request.clips)}개)",
        "created_at": datetime.now().isoformat(),
        "folder_id": folder_id  # 순차 폴더 ID 추가
    }
    job_status[job_id] = job_data
    
    # DB 저장 비활성화
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_batch_clipping,
        job_id,
        request
    )
    
    # API 응답 로깅
    response_time_ms = int((time.time() - request_start_time) * 1000)
    response = ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"배치 클리핑 작업이 시작되었습니다. (총 {len(request.clips)}개)"
    )
    
    # API 응답 업데이트 - DB 저장 비활성화
    
    return response


async def process_batch_clipping(job_id: str, request: BatchClippingRequest):
    """배치 비디오 클리핑 처리"""
    try:
        # 작업 시작
        update_job_status_both(job_id, "processing", 5, message="배치 클리핑 준비 중...")
        
        # DB 업데이트 비활성화
        
        # 단일 미디어 모드인 경우 미디어 경로 검증
        base_media_path = None
        if request.media_path:
            base_media_path = MediaValidator.validate_media_path(request.media_path)
            if not base_media_path:
                raise ValueError(f"Invalid media path: {request.media_path}")
            
        # DB 저장 비활성화
        
        # 날짜별 디렉토리 구조: /output/YYYY-MM-DD/folder_id
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        # job_status에서 folder_id 가져오기
        from api.utils.job_management import job_status
        folder_id = job_status.get(job_id, {}).get('folder_id', job_id)
        job_dir = daily_dir / folder_id
        job_dir.mkdir(exist_ok=True)
        
        output_files = []
        review_clip_path = None
        intro_clip_path = None
        
        # 인트로 비디오 생성 (include_intro가 True인 경우)
        if request.include_intro and request.intro_header_text:
            logger.info(f"[Job {job_id}] Creating intro video...")
            job_status[job_id]["progress"] = 3
            job_status[job_id]["message"] = "인트로 비디오 생성 중..."
            
            try:
                # 인트로 생성을 위한 임시 디렉토리
                intro_dir = job_dir / "intro"
                intro_dir.mkdir(exist_ok=True)
                
                # 인트로 비디오 생성 (intro.py의 로직 재사용)
                import subprocess
                import tempfile
                from pathlib import Path
                
                # TTS 생성
                edge_tts_path = "/home/kang/.local/bin/edge-tts"
                
                # 영어 TTS
                english_tts_path = intro_dir / "intro_en.mp3"
                english_tts_cmd = [
                    edge_tts_path,
                    "--voice", "en-US-AriaNeural",
                    "--rate", "+15%",
                    "--text", request.intro_header_text,
                    "--write-media", str(english_tts_path)
                ]
                subprocess.run(english_tts_cmd, check=True)
                
                # 한국어 TTS
                korean_text = request.intro_korean_text
                if request.intro_explanation:
                    korean_text += f". {request.intro_explanation}"
                
                korean_tts_path = intro_dir / "intro_ko.mp3"
                korean_tts_cmd = [
                    edge_tts_path,
                    "--voice", "ko-KR-SunHiNeural",
                    "--rate", "+10%",
                    "--text", korean_text,
                    "--write-media", str(korean_tts_path)
                ]
                subprocess.run(korean_tts_cmd, check=True)
                
                # 오디오 병합
                combined_tts_path = intro_dir / "intro_combined.mp3"
                concat_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(english_tts_path),
                    "-i", str(korean_tts_path),
                    "-filter_complex", "[0:a]apad=pad_dur=0.5[a0];[a0][1:a]concat=n=2:v=0:a=1[out]",
                    "-map", "[out]",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "48000",
                    "-ac", "2",
                    str(combined_tts_path)
                ]
                subprocess.run(concat_cmd, check=True)
                
                # 오디오 길이 확인
                duration_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(combined_tts_path)
                ]
                result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
                audio_duration = float(result.stdout.strip())
                
                # 비디오 포맷 결정 (템플릿에 따라)
                is_shorts = request.template_number in [11, 12, 13]
                width = 1080 if is_shorts else 1920
                height = 1920 if is_shorts else 1080
                video_format = "shorts" if is_shorts else "youtube"
                
                # 배경 이미지 처리 (첫 번째 클립의 미디어 사용)
                background_image = None
                if request.clips and request.intro_use_blur:
                    first_clip_media = request.clips[0].media_path or base_media_path
                    if first_clip_media:
                        validated_media = MediaValidator.validate_media_path(first_clip_media)
                        if validated_media:
                            # 썸네일 추출
                            thumbnail_path = intro_dir / "background.jpg"
                            extract_cmd = [
                                "ffmpeg", "-y",
                                "-i", str(validated_media),
                                "-ss", str(request.clips[0].start_time),
                                "-vframes", "1",
                                "-q:v", "1",
                                str(thumbnail_path)
                            ]
                            subprocess.run(extract_cmd, check=True)
                            if thumbnail_path.exists():
                                background_image = str(thumbnail_path)
                
                # ASS 자막 생성
                from api.routes.intro import create_ass_subtitle
                ass_path = await create_ass_subtitle(
                    english_text=request.intro_header_text,
                    korean_text=request.intro_korean_text,
                    duration=audio_duration,
                    output_path=intro_dir / "intro",
                    width=width,
                    height=height
                )
                
                # 비디오 생성
                intro_video_path = intro_dir / "intro.mp4"
                
                if background_image:
                    # 배경 이미지가 있는 경우
                    filter_str = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
                    
                    if request.intro_use_blur:
                        filter_str += ",eq=brightness=-0.7"
                    
                    if request.intro_use_gradient:
                        gradient_steps = 30
                        for i in range(gradient_steps):
                            x_pos = int(width * i / gradient_steps)
                            box_width = int(width / gradient_steps)
                            opacity = 0.6 * (1 - i / gradient_steps)
                            filter_str += f",drawbox={x_pos}:0:{box_width}:{height}:black@{opacity:.2f}:t=fill"
                    
                    filter_str += f",ass={ass_path}"
                    
                    # TemplateStandards와 동일한 인코딩 설정 사용 (특히 오디오)
                    ffmpeg_cmd = f"""ffmpeg -y -loop 1 -i "{background_image}" -i "{combined_tts_path}" -filter_complex "{filter_str}" -map 0:v -map 1:a -t {audio_duration} -c:v libx264 -preset veryfast -crf 23 -profile:v high -level 4.1 -pix_fmt yuv420p -g 60 -r 30 -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "{intro_video_path}" """
                else:
                    # 검은 배경
                    ffmpeg_cmd = f"""ffmpeg -y -f lavfi -i "color=c=black:s={width}x{height}:d={audio_duration}:r=30" -i "{combined_tts_path}" -vf "ass={ass_path}" -c:v libx264 -preset veryfast -crf 23 -profile:v high -level 4.1 -pix_fmt yuv420p -g 60 -r 30 -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart -shortest "{intro_video_path}" """
                
                subprocess.run(ffmpeg_cmd, shell=True, check=True)
                
                if intro_video_path.exists():
                    intro_clip_path = intro_video_path
                    logger.info(f"[Job {job_id}] Intro video created: {intro_clip_path}")
                
            except Exception as e:
                logger.error(f"[Job {job_id}] Intro video creation error: {e}")
                # 인트로 생성 실패해도 계속 진행
        
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
                    title_text=review_title,
                    is_preview=(request.study == "preview")
                )
                
                if success:
                    logger.info(f"[Job {job_id}] Study clip created: {review_clip_path}")
                    review_data = {
                        "file": str(review_clip_path),
                        "description": f"{mode_text} 클립"
                    }
                else:
                    logger.error(f"[Job {job_id}] Study clip creation failed")
            except Exception as e:
                logger.error(f"[Job {job_id}] Study clip error: {e}")
        
        # 개별 클립 처리
        for clip_num, clip_data in enumerate(request.clips, 1):
            job_status[job_id]["progress"] = 10 + int(80 * (clip_num - 1) / len(request.clips))
            job_status[job_id]["message"] = f"클립 {clip_num}/{len(request.clips)} 처리 중..."
            
            # 각 클립을 위한 디렉토리 생성
            clip_dir = job_dir / f"clip_{clip_num:03d}"
            clip_dir.mkdir(exist_ok=True)
            
            # 모든 템플릿에 대해 클립 생성
            text_eng_blank = None
            if request.template_number == 2 and clip_data.keywords:
                # 블랭크 텍스트 생성 로직은 Type 2에만 적용
                def wrap_text(text, max_chars=30):
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
            
            # 타이틀 로깅 추가 (모든 템플릿)
            logger.info(f"[Job {job_id}] Clip {clip_num} - title_1: '{request.title_1}', title_2: '{request.title_2}'")
            
            # 자막 데이터 (모든 템플릿)
            subtitle_data = {
                'start_time': 0,
                'end_time': clip_data.end_time - clip_data.start_time,
                'english': clip_data.text_eng,
                'korean': clip_data.text_kor,
                'note': clip_data.note,
                'eng': clip_data.text_eng,
                'kor': clip_data.text_kor,
                'is_shorts': request.template_number in [11, 12, 13],  # 쇼츠 여부
                'keywords': clip_data.keywords,  # Type 2를 위한 키워드
                'template_number': request.template_number,  # 클리핑 타입 전달
                'text_eng_blank': text_eng_blank,  # Type 2를 위한 blank 텍스트
                'title_1': request.title_1,  # 배치 전체 타이틀 첫 번째 줄
                'title_2': request.title_2,  # 배치 전체 타이틀 두 번째 줄
                'title_3': request.title_3   # 배치 전체 타이틀 세 번째 줄 (설명용)
            }
            
            # 비디오 클리핑 - 템플릿 기반 (자막 파일 자동 생성) (모든 템플릿)
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
            
            logger.info(f"[Job {job_id}] Clip {clip_num} - Using template: {template_name} (template_number: {request.template_number})")
            
            # 다중 미디어 모드 지원: 클립별 미디어 경로 또는 기본 미디어 경로 사용
            clip_media_path = clip_data.media_path if clip_data.media_path else base_media_path
            if not clip_media_path:
                raise ValueError(f"No media path specified for clip {clip_num}")
            
            # 미디어 경로 검증
            validated_media_path = MediaValidator.validate_media_path(clip_media_path)
            if not validated_media_path:
                raise ValueError(f"Invalid media path for clip {clip_num}: {clip_media_path}")
            
            # 템플릿을 사용하여 비디오 생성
            success = template_encoder.create_from_template(
                template_name=template_name,
                media_path=str(validated_media_path),
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
                
                # DB 저장 비활성화
            else:
                raise Exception(f"클립 {clip_num} 생성 실패")
            
            # DB 저장 비활성화
        
        # study 모드인 경우 preview는 처음에, review는 마지막에 추가
        if review_clip_path and review_clip_path.exists():
            review_entry = {
                "clip_number": 0 if request.study == "preview" else len(output_files) + 1,
                "file": str(Path(review_data["file"]).relative_to(OUTPUT_DIR.parent)),
                "text_eng": review_data["description"],
                "text_kor": review_data["description"]
            }
            if request.study == "preview":
                # preview는 맨 앞에 추가
                output_files.insert(0, review_entry)
            else:
                # review는 마지막에 추가
                output_files.append(review_entry)
        
        # 배치 렌더링 처리 (모든 템플릿에서 배치 생성 시)
        # 개별 클립이 1개 이상인 경우 배치 머지 수행
        individual_clips = [f for f in output_files if f["clip_number"] > 0 and f["clip_number"] < 999]
        logger.info(f"[Job {job_id}] Individual clips count: {len(individual_clips)}, output_files: {[f['clip_number'] for f in output_files]}")
        
        if len(individual_clips) >= 1:
            logger.info(f"[Job {job_id}] Starting batch rendering...")
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
            
            # 병합 순서 정리
            logger.info(f"[Job {job_id}] === 비디오 병합 순서 ===")
            
            # 1. 인트로가 있으면 맨 앞에 추가
            if intro_clip_path and intro_clip_path.exists():
                video_files.append(str(intro_clip_path))
                logger.info(f"[Job {job_id}] 1. 인트로: {intro_clip_path.name}")
            
            # 2. 나머지 클립들 추가 (순서대로)
            sorted_files = sorted(output_files, key=lambda x: x["clip_number"])
            for idx, file_info in enumerate(sorted_files):
                # 개별 클립 (1~998) 또는 study 클립 (0: preview, 999 이상: review)
                if file_info["clip_number"] != 999:  # 배치 파일 자체는 제외
                    full_path = OUTPUT_DIR.parent / file_info["file"]
                    if full_path.exists():
                        video_files.append(str(full_path))
                        clip_type = "Preview" if file_info["clip_number"] == 0 else ("Review" if file_info["clip_number"] > 900 else f"클립 {file_info['clip_number']}")
                        logger.info(f"[Job {job_id}] {len(video_files)}. {clip_type}: {full_path.name}")
            
            logger.info(f"[Job {job_id}] === 총 {len(video_files)}개 비디오 병합 예정 ===")
            
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
                
                # DB 저장 비활성화
        
        # 작업 완료
        # output_files를 먼저 설정
        job_status[job_id]["output_files"] = output_files
        
        # 그 다음에 상태 업데이트 (기존 output_files가 유지됨)
        update_job_status_both(
            job_id, 
            "completed", 
            100,
            message=f"배치 클리핑이 완료되었습니다. (총 {len(output_files)}개)"
        )
        
        # DB 업데이트 비활성화
        
        logger.info(f"[Job {job_id}] Batch clipping completed: {len(output_files)} files")
        
    except Exception as e:
        logger.error(f"[Job {job_id}] Batch clipping error: {str(e)}")
        update_job_status_both(
            job_id,
            "failed",
            0,
            message="배치 클리핑 실패",
            error_message=str(e)
        )
        
        # DB 업데이트 비활성화


def _get_subtitle_mode(template_number: int) -> str:
    """템플릿 번호로 자막 모드 추측"""
    if template_number == 1:
        return "nosub"
    elif template_number == 2:
        return "korean"
    elif template_number in [3, 11, 12, 13]:
        return "both"
    return "both"


@router.post("/clip/batch-multi",
             response_model=ClippingResponse,
             summary="다중 미디어 배치 클립 생성")
async def create_multi_media_batch_clips(
    request: MultimediaBatchRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    여러 미디어에서 클립을 추출하여 배치로 생성합니다.
    각 클립마다 개별 media_path가 필요합니다.
    """
    # BatchClippingRequest로 변환
    batch_request = BatchClippingRequest(
        media_path=None,  # 다중 미디어 모드이므로 None
        clips=request.clips,
        template_number=request.template_number,
        individual_clips=request.individual_clips,
        title_1=request.title_1,
        title_2=request.title_2,
        title_3=request.title_3,
        study=request.study
    )
    
    # 기존 배치 처리 함수 재사용
    return await create_batch_clips(batch_request, background_tasks, req)