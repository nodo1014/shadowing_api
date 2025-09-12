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

# Font paths
FONT_PATHS = {
    "english": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "korean": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "title": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
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
    format: str = Field("shorts", pattern="^(shorts|youtube)$", description="비디오 포맷")
    firstSentenceMediaInfo: Optional[FirstSentenceMediaInfo] = Field(None, description="첫 번째 문장의 미디어 정보")
    useBlur: Optional[bool] = Field(True, description="배경 흐림 효과 사용 여부")
    useGradient: Optional[bool] = Field(False, description="그라데이션 효과 사용 여부")


def escape_text(text: str) -> str:
    """FFmpeg drawtext를 위한 텍스트 이스케이프"""
    if not text or text.strip() == '':
        return 'NO_TEXT'
    
    # FFmpeg drawtext를 위한 이스케이프
    escaped = text
    escaped = escaped.replace(':', '\\:')
    escaped = escaped.replace('=', '\\=')
    escaped = escaped.replace(',', '\\,')
    escaped = escaped.replace(';', '\\;')
    escaped = escaped.replace('%', '\\%')
    escaped = escaped.replace('#', '\\#')
    escaped = escaped.replace('~', '\\~')
    escaped = escaped.replace('`', '\\`')
    escaped = escaped.replace('*', '\\*')
    escaped = escaped.replace('@', '\\@')
    escaped = escaped.replace('!', '\\!')
    escaped = escaped.replace('?', '\\?')
    escaped = escaped.replace('$', '\\$')
    escaped = escaped.replace('&', '\\&')
    escaped = escaped.replace('|', '\\|')
    escaped = escaped.replace('^', '\\^')
    escaped = escaped.replace('\\', '\\\\')
    escaped = escaped.replace('[', '\\[')
    escaped = escaped.replace(']', '\\]')
    escaped = escaped.replace('{', '\\{')
    escaped = escaped.replace('}', '\\}')
    escaped = escaped.replace('(', '\\(')
    escaped = escaped.replace(')', '\\)')
    escaped = escaped.replace('"', '\\"')
    
    # 작은따옴표를 Prime 문자로 대체
    if "'" in text:
        escaped = escaped.replace("'", "′")
    
    # 공백이 있거나 특수 문자가 있는 경우
    if ' ' in text or any(c in text for c in ['/', '<', '>', '~', '`', '!', '?']):
        return f"'{escaped}'"
    
    return escaped


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


async def extract_thumbnail_from_media(media_path: str, start_time: float, output_path: str) -> str:
    """미디어에서 썸네일 추출"""
    command = [
        "ffmpeg", "-y",
        "-i", media_path,
        "-ss", str(start_time),
        "-vframes", "1",
        "-q:v", "1",
        output_path
    ]
    
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract thumbnail: {e.stderr}")
        return None


async def generate_video_fade_in(params: dict) -> str:
    """Fade In 템플릿으로 비디오 생성"""
    english_text = escape_text(params['english_text'])
    korean_text = escape_text(params['korean_text'])
    audio_path = params['audio_path']
    output_path = params['output_path']
    duration = params['duration']
    background_image = params.get('background_image')
    use_blur = params.get('use_blur', True)
    use_gradient = params.get('use_gradient', False)
    width = params.get('width', 1080)
    height = params.get('height', 1920)
    
    if background_image:
        # 배경 이미지가 있는 경우
        # blur 대신 약간의 어두운 오버레이만 적용
        blur_filter = 'colorlevels=rimin=0:gimin=0:bimin=0:rimax=0.8:gimax=0.8:bimax=0.8,' if use_blur else ''
        # 왼쪽에서 오른쪽으로 검정 그라데이션 (중앙에서 시작)
        gradient_filter = f'drawbox=0:0:{width//2}:{height}:black:t=fill,drawbox={width//2}:0:{width//2}:{height}:black@0.3:t=fill,' if use_gradient else ''
        command = f"""ffmpeg -y \
          -loop 1 -i "{background_image}" \
          -i "{audio_path}" \
          -filter_complex "\
            [0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,\
            {blur_filter}
            {gradient_filter}\
            drawtext=text='스크린 영어 핵심 패턴':fontfile={FONT_PATHS['title']}:fontsize=80:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=150:alpha='if(lt(t,0.5),t/0.5,1)',\
            drawtext=text={english_text}:fontfile={FONT_PATHS['english']}:fontsize=120:fontcolor=0xFFD700:borderw=4:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2-140:shadowcolor=black:shadowx=5:shadowy=5:alpha='if(lt(t-0.3,0),0,if(lt(t-0.3,0.7),(t-0.3)/0.7,1))',\
            drawtext=text={korean_text}:fontfile={FONT_PATHS['korean']}:fontsize=75:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2+60:alpha='if(lt(t-0.6,0),0,if(lt(t-0.6,0.7),(t-0.6)/0.7,1))'\
          " \
          -map 0:v -map 1:a \
          -t {duration} \
          -c:v libx264 -preset fast -crf 23 \
          -c:a aac -b:a 192k \
          "{output_path}" """
    else:
        # 배경 이미지가 없는 경우
        command = f"""ffmpeg -y \
          -f lavfi -i "color=c=black:s={width}x{height}:d={duration}" \
          -i "{audio_path}" \
          -filter_complex "\
            [0:v]drawtext=text='스크린 영어 핵심 패턴':fontfile={FONT_PATHS['title']}:fontsize=80:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=150:alpha='if(lt(t,0.5),t/0.5,1)',\
            drawtext=text={english_text}:fontfile={FONT_PATHS['english']}:fontsize=140:fontcolor=0xFFD700:borderw=3:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2-120:shadowcolor=black:shadowx=3:shadowy=3:alpha='if(lt(t-0.3,0),0,if(lt(t-0.3,0.7),(t-0.3)/0.7,1))',\
            drawtext=text={korean_text}:fontfile={FONT_PATHS['korean']}:fontsize=90:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2+80:alpha='if(lt(t-0.6,0),0,if(lt(t-0.6,0.7),(t-0.6)/0.7,1))'\
          " \
          -c:v libx264 -preset fast -crf 23 \
          -c:a aac -b:a 192k \
          -shortest \
          "{output_path}" """
    
    return command


async def extract_thumbnail(video_path: str, output_path: str):
    """비디오에서 썸네일 추출"""
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", "0",
        "-vframes", "1", 
        "-q:v", "1",
        output_path
    ]
    
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"Thumbnail extracted: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Thumbnail extraction failed: {e.stderr}")


@router.post("/intro-videos")
async def create_intro_video(request: IntroVideoRequest):
    """인트로 비디오 생성 요청 (동기식 처리)"""
    try:
        logger.info("Starting intro video generation")
        logger.info(f"Request: {request.dict()}")
        
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
            thumbnail_path = output_dir / f"intro_bg_{unique_id}.jpg"
            background_image = await extract_thumbnail_from_media(
                request.firstSentenceMediaInfo.mediaPath, 
                request.firstSentenceMediaInfo.startTime,
                str(thumbnail_path)
            )
        
        # 비디오 생성 파라미터
        video_params = {
            'english_text': request.headerText,
            'korean_text': request.koreanText,
            'audio_path': str(tts_path),
            'output_path': str(video_path),
            'duration': audio_duration,
            'width': 1920 if request.format == 'youtube' else 1080,
            'height': 1080 if request.format == 'youtube' else 1920,
            'background_image': background_image,
            'use_blur': request.useBlur,
            'use_gradient': request.useGradient
        }
        
        # 템플릿에 따른 비디오 생성
        if request.template == "fade_in" or (request.template in ["shorts_thumbnail", "youtube_thumbnail"] and background_image):
            ffmpeg_command = await generate_video_fade_in(video_params)
        else:
            # 기본 템플릿 (fade_in 사용)
            ffmpeg_command = await generate_video_fade_in(video_params)
        
        # FFmpeg 실행
        logger.info(f"Executing FFmpeg command: {ffmpeg_command}")
        
        try:
            # shell=True를 사용하여 복잡한 명령어 실행
            result = subprocess.run(ffmpeg_command, shell=True, capture_output=True, text=True, check=True)
            logger.info(f"Video generated successfully: {video_path}")
            if result.stdout:
                logger.debug(f"FFmpeg stdout: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Video generation failed: {e.stderr}")
        
        # 썸네일 생성
        thumbnail_path = output_dir / f"intro_thumbnail_{unique_id}.jpg"
        await extract_thumbnail(str(video_path), str(thumbnail_path))
        
        # 결과 반환
        result_data = {
            "video": {
                "id": unique_id,
                "videoFilePath": str(video_path),
                "ttsFilePath": str(tts_path),
                "thumbnailPath": str(thumbnail_path),
                "duration": audio_duration,
                "headerText": request.headerText,
                "koreanText": request.koreanText,
                "format": request.format,
                "template": request.template
            },
            "status": "completed",
            "message": "인트로 영상 생성 완료"
        }
        
        logger.info(f"Intro video generation completed: {result_data}")
        return result_data
        
    except Exception as e:
        logger.error(f"Intro video generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intro-videos/{video_id}")
async def get_intro_video(video_id: str):
    """생성된 인트로 비디오 정보 조회"""
    output_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/intro_videos")
    video_path = output_dir / f"intro_video_{video_id}.mp4"
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    return {
        "id": video_id,
        "videoFilePath": str(video_path),
        "status": "available"
    }