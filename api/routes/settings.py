"""
Rendering settings API routes
렌더링 설정 관련 API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import json
import os
from pathlib import Path

router = APIRouter(prefix="/api/settings", tags=["settings"])

# 설정 파일 경로
SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "rendering_settings.json"
SETTINGS_FILE.parent.mkdir(exist_ok=True)

# 기본 설정값
DEFAULT_SETTINGS = {
    "tts": {
        "voice_korean": "ko-KR-SunHiNeural",
        "voice_english": "en-US-AriaNeural", 
        "speed": 0,  # -50 to +50
        "pitch": 0,  # -50 to +50 Hz
        "volume": 100  # 0 to 100
    },
    "video": {
        "crf": 16,  # 16-28
        "preset": "medium",  # ultrafast, fast, medium, slow, veryslow
        "resolution": "original",  # original, 720p, 1080p, 4k
        "framerate": 30  # 24, 30, 60
    },
    "subtitle": {
        "font_english": "Noto Sans CJK KR",
        "font_korean": "Noto Sans CJK KR",
        "size_english": 60,
        "size_korean": 50,
        "color_english": "#FFFFFF",
        "color_korean": "#FFD700",
        "border_width": 3,
        "border_color": "#000000",
        "position": "bottom",  # top, center, bottom
        "margin_bottom": 300
    },
    "template": {
        "gap_duration": 1.5,
        "fade_effect": False,
        "show_title": True,
        "background_music_volume": 20
    },
    "shorts": {
        "aspect_ratio": "center",  # center, origin, top, bottom, face, zoom, wide
        "thumbnail_darken": 10,  # 0-100
        "intro_duration": 3  # 1-5 seconds
    },
    "advanced": {
        "hardware_accel": "none",  # none, nvidia, amd
        "threads": 0,  # 0 = auto
        "temp_path": "/tmp",
        "output_format": "mp4"  # mp4, webm, mkv
    }
}

class TTSSettings(BaseModel):
    voice_korean: str = Field(..., description="한국어 TTS 음성")
    voice_english: str = Field(..., description="영어 TTS 음성") 
    speed: int = Field(0, ge=-50, le=50, description="속도 조절 (-50 ~ +50)")
    pitch: int = Field(0, ge=-50, le=50, description="피치 조절 (-50 ~ +50 Hz)")
    volume: int = Field(100, ge=0, le=100, description="볼륨 (0 ~ 100)")

class VideoSettings(BaseModel):
    crf: int = Field(16, ge=16, le=28, description="품질 (16-28, 낮을수록 고품질)")
    preset: str = Field("medium", description="인코딩 속도 프리셋")
    resolution: str = Field("original", description="해상도")
    framerate: int = Field(30, description="프레임레이트")

class SubtitleSettings(BaseModel):
    font_english: str = Field(..., description="영어 자막 폰트")
    font_korean: str = Field(..., description="한글 자막 폰트")
    size_english: int = Field(60, description="영어 자막 크기")
    size_korean: int = Field(50, description="한글 자막 크기")
    color_english: str = Field("#FFFFFF", description="영어 자막 색상")
    color_korean: str = Field("#FFD700", description="한글 자막 색상")
    border_width: int = Field(3, description="테두리 두께")
    border_color: str = Field("#000000", description="테두리 색상")
    position: str = Field("bottom", description="자막 위치")
    margin_bottom: int = Field(300, description="하단 여백")

class TemplateSettings(BaseModel):
    gap_duration: float = Field(1.5, ge=0, le=5, description="클립 간격 (초)")
    fade_effect: bool = Field(False, description="페이드 효과")
    show_title: bool = Field(True, description="제목 표시")
    background_music_volume: int = Field(20, ge=0, le=100, description="배경음악 볼륨")

class ShortsSettings(BaseModel):
    aspect_ratio: str = Field("center", description="크롭 방식")
    thumbnail_darken: int = Field(10, ge=0, le=100, description="썸네일 어둡게 (0-100%)")
    intro_duration: int = Field(3, ge=1, le=5, description="인트로 길이 (초)")

class AdvancedSettings(BaseModel):
    hardware_accel: str = Field("none", description="하드웨어 가속")
    threads: int = Field(0, ge=0, description="스레드 수 (0=자동)")
    temp_path: str = Field("/tmp", description="임시 파일 경로")
    output_format: str = Field("mp4", description="출력 형식")

class RenderingSettings(BaseModel):
    tts: TTSSettings
    video: VideoSettings
    subtitle: SubtitleSettings
    template: TemplateSettings
    shorts: ShortsSettings
    advanced: AdvancedSettings

def load_settings() -> Dict:
    """설정 파일 로드"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict):
    """설정 파일 저장"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

@router.get("/", response_model=RenderingSettings)
async def get_settings():
    """현재 렌더링 설정 조회"""
    settings = load_settings()
    return RenderingSettings(**settings)

@router.put("/", response_model=RenderingSettings)
async def update_settings(settings: RenderingSettings):
    """렌더링 설정 업데이트"""
    settings_dict = settings.dict()
    save_settings(settings_dict)
    return settings

@router.post("/reset", response_model=RenderingSettings)
async def reset_settings():
    """설정을 기본값으로 초기화"""
    save_settings(DEFAULT_SETTINGS)
    return RenderingSettings(**DEFAULT_SETTINGS)

@router.get("/tts/voices")
async def get_tts_voices():
    """사용 가능한 TTS 음성 목록"""
    return {
        "korean": [
            {"id": "ko-KR-SunHiNeural", "name": "Sun-Hi (여성)"},
            {"id": "ko-KR-InJoonNeural", "name": "InJoon (남성)"},
            {"id": "ko-KR-BongJinNeural", "name": "BongJin (남성)"},
            {"id": "ko-KR-GookMinNeural", "name": "GookMin (남성)"},
            {"id": "ko-KR-JiMinNeural", "name": "JiMin (여성)"},
            {"id": "ko-KR-SeoHyeonNeural", "name": "SeoHyeon (여성)"},
            {"id": "ko-KR-SoonBokNeural", "name": "SoonBok (여성)"},
            {"id": "ko-KR-YuJinNeural", "name": "YuJin (여성)"},
            {"id": "ko-KR-HyunsuNeural", "name": "Hyunsu (남성)"}
        ],
        "english": [
            {"id": "en-US-AriaNeural", "name": "Aria (여성)"},
            {"id": "en-US-JennyNeural", "name": "Jenny (여성)"},
            {"id": "en-US-GuyNeural", "name": "Guy (남성)"},
            {"id": "en-US-EricNeural", "name": "Eric (남성)"},
            {"id": "en-US-MichelleNeural", "name": "Michelle (여성)"},
            {"id": "en-US-RogerNeural", "name": "Roger (남성)"},
            {"id": "en-US-SteffanNeural", "name": "Steffan (남성)"}
        ]
    }

@router.get("/fonts")
async def get_available_fonts():
    """사용 가능한 폰트 목록"""
    # 시스템 폰트와 사용자 폰트 검색
    fonts = [
        {"id": "Noto Sans CJK KR", "name": "Noto Sans CJK KR"},
        {"id": "NanumGothic", "name": "나눔고딕"},
        {"id": "NanumBarunGothic", "name": "나눔바른고딕"},
        {"id": "Malgun Gothic", "name": "맑은 고딕"}
    ]
    
    # 사용자 폰트 디렉토리 확인
    user_fonts_dir = Path.home() / ".fonts"
    if user_fonts_dir.exists():
        for font_file in user_fonts_dir.glob("*.ttf"):
            font_name = font_file.stem
            fonts.append({
                "id": str(font_file),
                "name": font_name
            })
    
    return fonts

@router.get("/presets")
async def get_video_presets():
    """비디오 인코딩 프리셋 목록"""
    return [
        {"id": "ultrafast", "name": "초고속 (품질 낮음)"},
        {"id": "fast", "name": "빠름"},
        {"id": "medium", "name": "보통 (권장)"},
        {"id": "slow", "name": "느림 (품질 높음)"},
        {"id": "veryslow", "name": "매우 느림 (최고 품질)"}
    ]