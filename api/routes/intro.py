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
import re
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


async def generate_tts(text: str, language: str, output_path: str) -> float:
    """TTS 생성 함수"""
    config = TTS_CONFIG.get(language, TTS_CONFIG["english"])
    
    logger.info(f"[TTS] Generating TTS for: {text}")
    
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


async def create_ass_subtitle(english_text: str, korean_text: str, duration: float, output_path: Path, width: int = 1080, height: int = 1920) -> Path:
    """ASS 자막 파일 생성"""
    # 텍스트 정리 - 순수 텍스트만 사용
    english_text = english_text.strip()
    korean_text = korean_text.strip()
    
    # ASS 파일을 위한 텍스트 이스케이프
    # 중괄호만 이스케이프하여 ASS 제어 코드로 해석되지 않도록 함
    english_text_escaped = english_text.replace('{', '\\{').replace('}', '\\}')
    korean_text_escaped = korean_text.replace('{', '\\{').replace('}', '\\}')
    
    # 원본 텍스트 로그
    logger.info(f"[ASS] English text: '{english_text}'")
    logger.info(f"[ASS] Korean text: '{korean_text}'")
    # 쇼츠(세로)와 유튜브(가로) 형식에 따른 위치 조정
    if width > height:  # 가로 형식 (YouTube)
        # YouTube 사이즈
        title_size = 65
        title_margin = 100
        english_size = 110
        english_margin = 280
        korean_size = 70
        korean_margin = 480
    else:  # 세로 형식 (Shorts)
        # Shorts 사이즈
        title_size = 90
        title_margin = 180
        english_size = 130
        english_margin = 750
        korean_size = 80
        korean_margin = 1050
    
    ass_content = f"""[Script Info]
Title: Intro Subtitle
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,TmonMonsori,{title_size},&H00F5F5F5,&H000000FF,&H20000000,&H80000000,0,0,0,0,100,100,2,0,1,4,6,8,100,100,{title_margin},1
Style: English,Noto Sans CJK KR,{english_size},&H0000CCFF,&H000000FF,&H20000000,&HB0000000,1,0,0,0,100,100,0,0,1,5,8,5,120,120,{english_margin},1
Style: Korean,Noto Sans CJK KR,{korean_size},&H00FFFFFF,&H000000FF,&H40000000,&HA0000000,1,0,0,0,100,100,1,0,1,4,6,5,120,120,{korean_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:{duration:.2f},Title,,0,0,0,,{{\\fad(600,600)\\bord4\\shad6\\be2\\blur1\\3c&H404040&\\4c&HA0000000&}}스크린 영어 핵심 패턴
Dialogue: 0,0:00:00.40,0:00:{duration:.2f},English,,0,0,0,,{{\\fad(800,600)\\bord5\\shad8\\be2\\blur2\\3c&H000000&\\4c&HC0000000&\\fscx105\\fscy105}}{english_text_escaped}
Dialogue: 0,0:00:00.80,0:00:{duration:.2f},Korean,,0,0,0,,{{\\fad(800,600)\\bord4\\shad6\\be1\\blur1\\3c&H202020&\\4c&HB0000000&}}{korean_text_escaped}
"""
    
    ass_path = output_path.parent / f"{output_path.stem}_subtitle.ass"
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    logger.info(f"[ASS] File created: {ass_path}")
    
    return ass_path


async def generate_video_fade_in(params: dict) -> str:
    """Fade In 템플릿으로 비디오 생성"""
    english_text = params['english_text']
    korean_text = params['korean_text']
    audio_path = params['audio_path']
    output_path = params['output_path']
    duration = params['duration']
    background_image = params.get('background_image')
    use_blur = params.get('use_blur', True)
    use_gradient = params.get('use_gradient', False)
    width = params.get('width', 1080)
    height = params.get('height', 1920)
    
    # ASS 자막 파일 생성
    ass_path = await create_ass_subtitle(
        english_text=english_text,
        korean_text=korean_text,
        duration=duration,
        output_path=Path(output_path),
        width=width,
        height=height
    )
    logger.info(f"[ASS] Subtitle file created: {ass_path}")
    
    if background_image:
        # 배경 이미지가 있는 경우
        filter_str = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
        
        if use_blur:
            filter_str += ",colorlevels=rimin=0:gimin=0:bimin=0:rimax=0.8:gimax=0.8:bimax=0.8"
        
        if use_gradient:
            filter_str += f",drawbox=0:0:{width//2}:{height}:black:t=fill,drawbox={width//2}:0:{width//2}:{height}:black@0.3:t=fill"
        
        # ASS 자막 추가
        ass_path_str = str(ass_path)
        filter_str += f",ass={ass_path_str}"
        
        command = f"""ffmpeg -y -loop 1 -i "{background_image}" -i "{audio_path}" -filter_complex "{filter_str}" -map 0:v -map 1:a -t {duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 192k "{output_path}" """
    else:
        # 배경 이미지가 없는 경우
        ass_path_str = str(ass_path)
        command = f"""ffmpeg -y -f lavfi -i "color=c=black:s={width}x{height}:d={duration}" -i "{audio_path}" -vf "ass={ass_path_str}" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 192k -shortest "{output_path}" """
    
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
        
        # 날짜별 디렉토리 생성
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        unique_suffix = uuid.uuid4().hex[:6]
        
        # 기본 출력 디렉토리
        base_output_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/intro_videos")
        
        # 날짜별 디렉토리
        date_dir = base_output_dir / date_str
        
        # 시간별 작업 디렉토리 (각 요청마다 고유한 폴더)
        job_dir = date_dir / f"{time_str}_{unique_suffix}"
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # 작업 ID (폴더명과 동일)
        job_id = f"{time_str}_{unique_suffix}"
        
        # TTS 파일 경로 설정
        english_tts_path = job_dir / "audio_en.mp3"
        korean_tts_path = job_dir / "audio_ko.mp3"
        tts_path = job_dir / "audio_combined.mp3"
        
        # 1. 영어 패턴 문장 TTS 생성
        logger.info(f"[TTS] 영어 TTS 생성 시작: {request.headerText}")
        english_duration = await generate_tts(request.headerText, "english", str(english_tts_path))
        logger.info(f"[TTS] 영어 TTS 생성 완료: {english_tts_path} (길이: {english_duration:.2f}초)")
        
        # 파일 존재 확인
        if not english_tts_path.exists():
            logger.error(f"[TTS] 영어 TTS 파일 생성 실패: {english_tts_path}")
        
        # 2. 한글 설명 TTS 생성
        korean_text = request.koreanText
        if request.explanation:
            korean_text += f". {request.explanation}"
        
        logger.info(f"[TTS] 한글 TTS 생성 시작: {korean_text[:50]}...")
        korean_duration = await generate_tts(korean_text, "korean", str(korean_tts_path))
        logger.info(f"[TTS] 한글 TTS 생성 완료: {korean_tts_path} (길이: {korean_duration:.2f}초)")
        
        # 파일 존재 확인
        if not korean_tts_path.exists():
            logger.error(f"[TTS] 한글 TTS 파일 생성 실패: {korean_tts_path}")
        
        # 3. 두 오디오 파일을 연결 (0.5초 간격 추가)
        concat_command = [
            "ffmpeg", "-y",
            "-i", str(english_tts_path),
            "-i", str(korean_tts_path),
            "-filter_complex", 
            "[0:a]apad=pad_dur=0.5[a0];[a0][1:a]concat=n=2:v=0:a=1[out]",
            "-map", "[out]",
            str(tts_path)
        ]
        
        logger.info(f"[TTS] 오디오 연결 시작: {english_tts_path.name} + {korean_tts_path.name} -> {tts_path.name}")
        
        try:
            result = subprocess.run(concat_command, capture_output=True, text=True, check=True)
            logger.info(f"[TTS] 오디오 연결 성공: {tts_path}")
            
            # 최종 파일 크기 확인
            if tts_path.exists():
                file_size_kb = tts_path.stat().st_size / 1024
                logger.info(f"[TTS] 최종 오디오 파일: {tts_path.name} ({file_size_kb:.2f}KB)")
            
            # 임시 파일 삭제
            english_tts_path.unlink()
            korean_tts_path.unlink()
        except subprocess.CalledProcessError as e:
            logger.error(f"[TTS] 오디오 연결 실패: {e.stderr}")
            # concat 실패 시 한국어만 사용
            korean_tts_path.rename(tts_path)
            if english_tts_path.exists():
                english_tts_path.unlink()
        
        # 전체 오디오 길이 계산
        audio_duration = english_duration + 0.5 + korean_duration
        logger.info(f"[TTS] 전체 오디오 길이: {audio_duration:.2f}초")
        
        # 비디오 생성 파라미터 설정
        video_path = job_dir / "intro_video.mp4"
        
        # 배경 이미지 처리
        background_image = None
        if request.firstSentenceMediaInfo:
            # 첫 번째 문장의 미디어에서 썸네일 추출 (모든 템플릿에서 사용 가능)
            bg_thumbnail_path = job_dir / "background.jpg"
            background_image = await extract_thumbnail_from_media(
                request.firstSentenceMediaInfo.mediaPath, 
                request.firstSentenceMediaInfo.startTime,
                str(bg_thumbnail_path)
            )
        
        # TTS 파일이 FFmpeg에 전달되는지 확인
        if not tts_path.exists():
            logger.error(f"[FFmpeg] TTS 파일이 존재하지 않음: {tts_path}")
            raise HTTPException(status_code=500, detail=f"TTS file not found: {tts_path}")
        
        logger.info(f"[FFmpeg] 비디오 생성 준비 - TTS 파일: {tts_path} (존재: {tts_path.exists()})")
        
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
        
        logger.info(f"[FFmpeg] 비디오 파라미터: format={request.format}, duration={audio_duration:.2f}s, resolution={video_params['width']}x{video_params['height']}")
        
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
        thumbnail_path = job_dir / "thumbnail.jpg"
        await extract_thumbnail(str(video_path), str(thumbnail_path))
        
        # 결과 반환 (폴더 구조 정보 포함)
        result_data = {
            "video": {
                "id": job_id,
                "jobFolder": str(job_dir),
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
    base_output_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/intro_videos")
    
    # video_id는 'HHMMSS_unique' 형식이므로, 날짜별 폴더를 검색해야 함
    # 최근 7일간의 폴더를 검색
    from datetime import datetime, timedelta
    
    for days_back in range(7):
        date = datetime.now() - timedelta(days=days_back)
        date_str = date.strftime("%Y-%m-%d")
        date_dir = base_output_dir / date_str
        
        if date_dir.exists():
            job_dir = date_dir / video_id
            if job_dir.exists():
                video_path = job_dir / "intro_video.mp4"
                if video_path.exists():
                    return {
                        "id": video_id,
                        "jobFolder": str(job_dir),
                        "videoFilePath": str(video_path),
                        "thumbnailPath": str(job_dir / "thumbnail.jpg"),
                        "ttsFilePath": str(job_dir / "audio_combined.mp3"),
                        "status": "available"
                    }
    
    raise HTTPException(status_code=404, detail="Video not found")


class MergeVideosRequest(BaseModel):
    """비디오 병합 요청"""
    videoPaths: list[str] = Field(..., description="병합할 비디오 파일 경로 리스트")
    outputFileName: str = Field(..., description="출력 파일명")
    
    
@router.post("/merge-videos")
async def merge_videos(request: MergeVideosRequest):
    """여러 비디오를 하나로 병합"""
    try:
        logger.info(f"[Merge] 병합 시작 - 파일 수: {len(request.videoPaths)}")
        logger.info(f"[Merge] 입력 파일: {request.videoPaths}")
        logger.info(f"[Merge] 출력 파일명: {request.outputFileName}")
        
        # 출력 디렉토리 설정
        output_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/merged")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 출력 파일 경로
        output_path = output_dir / request.outputFileName
        logger.info(f"[Merge] 출력 경로: {output_path}")
        
        # concat 파일 생성
        concat_file = output_dir / f"concat_{uuid.uuid4().hex}.txt"
        logger.info(f"[Merge] Concat 파일 생성: {concat_file}")
        
        with open(concat_file, 'w') as f:
            for idx, video_path in enumerate(request.videoPaths, 1):
                # 경로 검증
                if not Path(video_path).exists():
                    logger.error(f"[Merge] 파일 없음: {video_path}")
                    raise HTTPException(status_code=404, detail=f"Video not found: {video_path}")
                
                # 파일 크기 확인
                file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                logger.info(f"[Merge] 입력 파일 {idx}: {Path(video_path).name} ({file_size_mb:.2f}MB)")
                f.write(f"file '{video_path}'\n")
        
        # 첫 번째 비디오의 속성 확인 (해상도, fps 기준)
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json",
            request.videoPaths[0]
        ]
        
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(probe_result.stdout)
        
        if probe_data.get("streams"):
            video_info = probe_data["streams"][0]
            width = video_info.get("width", 1080)
            height = video_info.get("height", 1920)
            
            # fps 계산
            r_frame_rate = video_info.get("r_frame_rate", "25/1")
            fps_parts = r_frame_rate.split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 25
        else:
            # 기본값
            width, height, fps = 1080, 1920, 25
        
        logger.info(f"[Merge] 비디오 속성: {width}x{height} @ {fps}fps")
        
        # FFmpeg로 병합 (re-encoding으로 통일)
        command = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path)
        ]
        
        logger.info(f"[Merge] FFmpeg 명령 실행 시작...")
        start_time = datetime.now()
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[Merge] FFmpeg 병합 완료 - 소요시간: {elapsed_time:.2f}초")
        
        # concat 파일 삭제
        concat_file.unlink()
        
        # 출력 파일 정보
        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"[Merge] 최종 파일 생성 완료: {output_path.name} ({output_size_mb:.2f}MB)")
        logger.info(f"[Merge] ✅ 병합 프로세스 완료 - 총 소요시간: {elapsed_time:.2f}초")
        
        return {
            "success": True,
            "outputPath": str(output_path),
            "message": "비디오 병합 완료"
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[Merge] ❌ FFmpeg 병합 실패: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Video merge failed: {e.stderr}")
    except Exception as e:
        logger.error(f"[Merge] ❌ 병합 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))