"""
Mixed Template Routes - 여러 템플릿을 혼합하여 사용
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
import uuid
import logging
from datetime import datetime
from pathlib import Path
import tempfile
import subprocess

from api.models import MixedTemplateRequest, ClippingResponse, SubtitleInfo
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import (
    generate_blank_text, 
    update_job_status_both,
    job_status,
    cleanup_memory_jobs
)
# Using text_processing.py's create_multi_subtitle_file which now uses ASSGenerator
from api.utils.text_processing import create_multi_subtitle_file

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from template_video_encoder import TemplateVideoEncoder
# No longer need get_ass_styles_section as we use extract.py's function

router = APIRouter(prefix="/api", tags=["Clipping"])
logger = logging.getLogger(__name__)


@router.post("/clip/mixed",
             response_model=ClippingResponse,
             summary="혼합 템플릿 클립 생성")
async def create_mixed_template_clips(
    request: MixedTemplateRequest,
    background_tasks: BackgroundTasks
):
    """
    각 클립에 다른 템플릿을 적용하여 생성합니다.
    
    예시:
    - 클립1: template_1 (기본)
    - 클립2: template_2 (키워드 블랭크)  
    - 클립3: template_3 (점진적 학습)
    
    combine=True면 하나의 비디오로 결합합니다.
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # Debug logging
    logger.info(f"[Job {job_id}] Mixed template request - Clips: {len(request.clips)}, Combine: {request.combine}")
    for i, clip in enumerate(request.clips):
        logger.info(f"  Clip {i+1}: Template {clip.template_number}, {clip.start_time}-{clip.end_time}s")
    
    # 메모리 정리
    cleanup_memory_jobs()
    
    # 작업 상태 초기화
    job_status[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "혼합 템플릿 작업 대기 중...",
        "output_files": [],
        "combined_file": None,
        "total_clips": len(request.clips),
        "completed_clips": 0,
        "error": None
    }
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_mixed_clips,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"혼합 템플릿 작업이 시작되었습니다. (총 {len(request.clips)}개)"
    )


async def process_mixed_clips(job_id: str, request: MixedTemplateRequest):
    """혼합 템플릿 클립 처리"""
    try:
        # 작업 시작
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "혼합 템플릿 클립 준비 중..."
        
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
        
        output_files = []
        template_encoder = TemplateVideoEncoder()
        
        # 각 클립을 해당 템플릿으로 생성
        for idx, clip_data in enumerate(request.clips):
            clip_num = idx + 1
            job_status[job_id]["progress"] = int((idx / len(request.clips)) * 80)
            job_status[job_id]["message"] = f"클립 {clip_num}/{len(request.clips)} 처리 중 (템플릿 {clip_data.template_number})..."
            
            # Template 0 또는 10 (구간 추출)인 경우
            if clip_data.template_number in [0, 10]:
                # 자막 파일 생성
                ass_path = job_dir / f"subtitles_c{clip_num:03d}.ass"
                is_shorts = clip_data.template_number == 10
                # SubtitleInfo를 dict로 변환
                subtitle_dicts = [
                    {
                        'start': sub.start,
                        'end': sub.end,
                        'eng': sub.eng,
                        'kor': sub.kor
                    }
                    for sub in clip_data.subtitles
                ]
                create_multi_subtitle_file(ass_path, subtitle_dicts, clip_data.start_time, is_shorts=is_shorts)
                
                # 자막 데이터 준비 (구간 추출용)
                subtitle_data = {
                    'start_time': 0,
                    'end_time': clip_data.end_time - clip_data.start_time,
                    'subtitles': clip_data.subtitles,
                    'ass_file': str(ass_path),
                    'template_number': clip_data.template_number
                }
            else:
                # 텍스트 블랭크 처리 (템플릿 2인 경우)
                text_eng_blank = None
                if clip_data.template_number == 2:
                    text_eng_blank = generate_blank_text(clip_data.text_eng, clip_data.keywords)
                
                # 자막 데이터 준비 (학습용)
                subtitle_data = {
                    'start_time': 0,
                    'end_time': clip_data.end_time - clip_data.start_time,
                    'english': clip_data.text_eng,
                    'korean': clip_data.text_kor,
                    'note': clip_data.note,
                    'eng': clip_data.text_eng,
                    'kor': clip_data.text_kor,
                    'keywords': clip_data.keywords,
                    'template_number': clip_data.template_number,
                    'text_eng_blank': text_eng_blank
                }
            
            # 템플릿 이름 결정
            if clip_data.template_number in TEMPLATE_MAPPING:
                template_name = TEMPLATE_MAPPING[clip_data.template_number]
            else:
                template_name = f"template_{clip_data.template_number}"
            
            # 개별 클립 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_tp_{clip_data.template_number}_c{clip_num:03d}.mp4"
            output_path = job_dir / filename
            
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
            
            if success and output_path.exists():
                file_info = {
                    "clip_number": clip_num,
                    "file": str(output_path),
                    "template": clip_data.template_number
                }
                # Template 0이 아닌 경우만 text_eng/text_kor 추가
                if clip_data.template_number != 0:
                    file_info["text_eng"] = clip_data.text_eng
                    file_info["text_kor"] = clip_data.text_kor
                output_files.append(file_info)
                job_status[job_id]["completed_clips"] = clip_num
                logger.info(f"[Job {job_id}] Clip {clip_num} created with template {clip_data.template_number}")
            else:
                raise Exception(f"클립 {clip_num} 생성 실패 (템플릿 {clip_data.template_number})")
        
        # 결합 옵션이 True인 경우
        if request.combine and len(output_files) > 1:
            job_status[job_id]["progress"] = 85
            job_status[job_id]["message"] = "비디오 결합 중..."
            
            # 결합된 비디오 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_filename = f"{timestamp}_mixed_combined.mp4"
            combined_path = job_dir / combined_filename
            
            # 비디오 결합
            success = await combine_videos(
                video_files=[Path(f["file"]) for f in output_files],
                output_path=combined_path,
                transitions=request.transitions
            )
            
            if success and combined_path.exists():
                # output 폴더 기준 상대 경로
                rel_path = combined_path.relative_to(OUTPUT_DIR)
                job_status[job_id]["combined_file"] = str(rel_path)
                logger.info(f"[Job {job_id}] Videos combined successfully: {combined_path}")
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        job_status[job_id]["message"] = f"혼합 템플릿 클립 생성 완료! (총 {len(output_files)}개)"
        job_status[job_id]["output_files"] = output_files
        
        # Redis에 동기화
        from api.utils.job_management import USE_REDIS, redis_client, JOB_EXPIRE_TIME
        if USE_REDIS and redis_client:
            try:
                import pickle
                redis_client.setex(
                    f"job_status:{job_id}",
                    JOB_EXPIRE_TIME,
                    pickle.dumps(job_status[job_id])
                )
            except Exception as e:
                logger.warning(f"Redis sync failed: {e}")
        
        # 메인 출력 파일 설정
        if request.combine and job_status[job_id].get("combined_file"):
            job_status[job_id]["output_file"] = job_status[job_id]["combined_file"]
        elif len(output_files) == 1:
            job_status[job_id]["output_file"] = output_files[0]["file"]
        
        logger.info(f"[Job {job_id}] Mixed template processing completed: {len(output_files)} files")
    
    except Exception as e:
        logger.error(f"[Job {job_id}] Mixed template error: {str(e)}")
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = "혼합 템플릿 생성 실패"


async def combine_videos(video_files: List[Path], output_path: Path, transitions: bool = False) -> bool:
    """여러 비디오를 하나로 결합"""
    try:
        if transitions:
            # 트랜지션 효과가 있는 결합 (나중에 구현)
            logger.warning("Transition effects not implemented yet, using simple concat")
        
        # 각 비디오 파일 정보 로깅
        for i, video_file in enumerate(video_files):
            logger.info(f"Video {i+1}: {video_file} (exists: {video_file.exists()}, size: {video_file.stat().st_size if video_file.exists() else 0})")
        
        # concat demuxer를 위한 임시 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for video_file in video_files:
                # 상대 경로 대신 절대 경로 사용
                f.write(f"file '{str(video_file.absolute())}'\n")
            concat_file = f.name
            
        # concat 파일 내용 확인
        with open(concat_file, 'r') as f:
            logger.info(f"Concat file contents:\n{f.read()}")
        
        # 비디오 수가 적을 때는 filter_complex 사용 (더 안정적)
        if len(video_files) <= 5:
            # filter_complex를 사용한 결합
            cmd = ['ffmpeg', '-y']
            filter_parts = []
            
            # 각 비디오를 입력으로 추가
            for i, video_file in enumerate(video_files):
                cmd.extend(['-i', str(video_file)])
                filter_parts.append(f"[{i}:v:0][{i}:a:0]")
            
            # concat 필터 구성
            filter_str = "".join(filter_parts) + f"concat=n={len(video_files)}:v=1:a=1[outv][outa]"
            
            cmd.extend([
                '-filter_complex', filter_str,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '22',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                str(output_path)
            ])
        else:
            # 많은 파일일 때는 concat demuxer 사용
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264',  # 비디오 재인코딩
                '-preset', 'fast',
                '-crf', '22',
                '-c:a', 'aac',  # 오디오 재인코딩
                '-b:a', '192k',
                '-movflags', '+faststart',
                str(output_path)
            ]
        
        logger.info(f"Combining videos: {' '.join(cmd)}")
        
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: subprocess.run(cmd, capture_output=True, text=True)
        )
        
        # 임시 파일 삭제
        Path(concat_file).unlink()
        
        if result.returncode != 0:
            logger.error(f"FFmpeg concat error: {result.stderr}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Video combination error: {e}")
        return False


# Removed duplicate create_multi_subtitle_file function - now using the one from extract.py