"""
Intro video generation routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path
import uuid
import logging
import os
import subprocess
import json
from datetime import datetime

# Import from adapters
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from database_adapter import save_job_to_db, update_job_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["intro"])

# TTS Configuration
TTS_CONFIG = {
    "english": {
        "voice": "en-US-AriaNeural",
        "rate": "+15%",
        "volume": "+0%"
    },
    "korean": {
        "voice": "ko-KR-SunHiNeural",
        "rate": "+10%",
        "volume": "+0%"
    }
}

class FirstSentenceMediaInfo(BaseModel):
    """첫 번째 문장의 미디어 정보"""
    mediaPath: str = Field(..., description="미디어 파일 경로")
    startTime: float = Field(..., ge=0, description="시작 시간 (초)")

class IntroVideoRequest(BaseModel):
    """인트로 비디오 생성 요청"""
    projectId: Optional[str] = Field(None, description="프로젝트 ID")
    headerText: str = Field(..., min_length=1, description="영어 헤더 텍스트")
    koreanText: str = Field(..., min_length=1, description="한국어 텍스트")
    explanation: Optional[str] = Field("", description="설명 텍스트")
    template: str = Field("fade_in", description="템플릿 타입")
    format: str = Field("shorts", regex="^(shorts|youtube)$", description="비디오 포맷")
    firstSentenceMediaInfo: Optional[FirstSentenceMediaInfo] = Field(None, description="첫 번째 문장의 미디어 정보")
    useBlur: Optional[bool] = Field(True, description="배경 흐림 효과 사용 여부")


async def generate_tts(text: str, language: str, output_path: str) -> float:
    """TTS 생성 함수"""
    config = TTS_CONFIG.get(language, TTS_CONFIG["english"])
    
    # edge-tts 명령어로 음성 생성
    edge_tts_path = "/home/kang/.local/bin/edge-tts"
    command = [
        edge_tts_path,
        "--voice", config["voice"],
        "--rate", config["rate"],
        "--volume", config["volume"],
        "--text", text,
        "--write-media", output_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"TTS generated: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"TTS generation failed: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e.stderr}")
    
    # FFprobe로 오디오 길이 확인
    duration_command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        output_path
    ]
    
    try:
        result = subprocess.run(duration_command, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        return 0.0


async def extract_thumbnail(video_path: str, start_time: float = 0) -> str:
    """비디오에서 썸네일 추출"""
    output_path = video_path.replace(".mp4", "_thumbnail.jpg")
    
    command = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        output_path
    ]
    
    try:
        subprocess.run(command, capture_output=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract thumbnail: {e.stderr}")
        return None


async def process_intro_video(job_id: str, request: IntroVideoRequest):
    """인트로 비디오 생성 프로세스"""
    try:
        logger.info(f"Starting intro video generation for job {job_id}")
        update_job_status(job_id, "processing", {"message": "인트로 영상 생성 중..."})
        
        # 출력 디렉토리 설정
        output_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/intro_videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 고유 ID 생성
        unique_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # TTS 생성
        tts_path = output_dir / f"intro_tts_{unique_id}.mp3"
        
        # 영어와 한국어 텍스트 결합
        combined_text = f"{request.headerText}. {request.koreanText}"
        if request.explanation:
            combined_text += f". {request.explanation}"
        
        audio_duration = await generate_tts(combined_text, "korean", str(tts_path))
        
        # 비디오 생성 파라미터 설정
        video_path = output_dir / f"intro_video_{unique_id}.mp4"
        
        # 배경 이미지 처리
        background_image = None
        if request.firstSentenceMediaInfo and request.template in ["shorts_thumbnail", "youtube_thumbnail"]:
            # 첫 번째 문장의 미디어에서 썸네일 추출
            thumbnail_path = await extract_thumbnail(
                request.firstSentenceMediaInfo.mediaPath, 
                request.firstSentenceMediaInfo.startTime
            )
            if thumbnail_path:
                background_image = thumbnail_path
        
        # FFmpeg 명령어 구성
        width = 1920 if request.format == "youtube" else 1080
        height = 1080 if request.format == "youtube" else 1920
        
        # 기본 템플릿 설정
        if request.template == "fade_in":
            # 페이드 인 효과 템플릿
            filter_complex = f"""
            [0:v] scale={width}:{height}:force_original_aspect_ratio=decrease,
            pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,
            fade=t=in:st=0:d=1
            """
        elif request.template in ["shorts_thumbnail", "youtube_thumbnail"] and background_image:
            # 썸네일 배경 템플릿
            blur_filter = ",gblur=sigma=20" if request.useBlur else ""
            filter_complex = f"""
            [0:v] scale={width}:{height}:force_original_aspect_ratio=increase,
            crop={width}:{height}{blur_filter}
            """
        else:
            # 기본 템플릿
            filter_complex = f"scale={width}:{height}"
        
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={audio_duration}",
            "-i", str(tts_path),
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(video_path)
        ]
        
        # 배경 이미지가 있는 경우 입력으로 추가
        if background_image:
            ffmpeg_command.insert(3, "-i")
            ffmpeg_command.insert(4, background_image)
            # filter_complex 인덱스 조정
            filter_complex = filter_complex.replace("[0:v]", "[1:v]")
            ffmpeg_command[ffmpeg_command.index("-filter_complex") + 1] = filter_complex
        
        # FFmpeg 실행
        try:
            result = subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
            logger.info(f"Video generated: {video_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise Exception(f"Video generation failed: {e.stderr}")
        
        # 결과 저장
        result_data = {
            "id": unique_id,
            "videoFilePath": str(video_path),
            "ttsFilePath": str(tts_path),
            "duration": audio_duration,
            "headerText": request.headerText,
            "koreanText": request.koreanText,
            "format": request.format,
            "template": request.template
        }
        
        update_job_status(job_id, "completed", {
            "message": "인트로 영상 생성 완료",
            "result": result_data
        })
        
        logger.info(f"Intro video generation completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Intro video generation failed for job {job_id}: {str(e)}")
        update_job_status(job_id, "failed", {
            "message": "인트로 영상 생성 실패",
            "error": str(e)
        })


@router.post("/intro-videos")
async def create_intro_video(
    request: IntroVideoRequest,
    background_tasks: BackgroundTasks
):
    """인트로 비디오 생성 요청"""
    try:
        # Job ID 생성
        job_id = str(uuid.uuid4())
        
        # Job 정보 저장
        job_data = {
            "id": job_id,
            "type": "intro_video",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "request_data": request.dict()
        }
        
        save_job_to_db(job_id, job_data)
        
        # 백그라운드 작업 추가
        background_tasks.add_task(process_intro_video, job_id, request)
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "인트로 영상 생성 작업이 시작되었습니다."
        }
        
    except Exception as e:
        logger.error(f"Failed to create intro video job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intro-videos/job/{job_id}")
async def get_intro_video_status(job_id: str):
    """인트로 비디오 생성 작업 상태 조회"""
    try:
        # Job 상태 조회 (실제 구현에서는 DB에서 조회)
        # 여기서는 간단한 예시
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "작업 진행 중..."
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job not found")