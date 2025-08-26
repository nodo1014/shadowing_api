"""
Request Models for Video Clipping API
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from .validators import MediaValidator


class ClipData(BaseModel):
    """개별 클립 데이터"""
    start_time: float = Field(..., ge=0, description="클립 시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="클립 종료 시간 (초)")
    text_eng: str = Field(..., description="영문 자막")
    text_kor: str = Field(..., description="한글 자막")
    note: Optional[str] = Field(None, description="메모")
    keywords: Optional[List[str]] = Field(None, description="키워드 리스트")
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v


class ClippingRequest(ClipData):
    """단일 클리핑 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호 (1-3: 일반, 11-13: 쇼츠, 21-29: TTS, 31-39: 스터디클립)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        # 미디어 경로 검증
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v


class BatchClippingRequest(BaseModel):
    """배치 클리핑 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    clips: List[ClipData] = Field(..., description="클립 데이터 리스트")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호 (1-3: 일반, 11-13: 쇼츠, 21-29: TTS, 31-39: 스터디클립)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")
    title_1: Optional[str] = Field(None, description="타이틀 첫 번째 줄 (쇼츠: 흰색 120pt, 일반: 왼쪽 흰색 40pt)")
    title_2: Optional[str] = Field(None, description="타이틀 두 번째 줄 (쇼츠: 골드 90pt, 일반: 오른쪽 흰색 40pt)")
    title_3: Optional[str] = Field(None, description="타이틀 세 번째 줄 (쇼츠 템플릿 2,3용: 흰색 60pt, \\n 지원)")
    study: Optional[str] = Field(None, description="학습 모드 (preview: 맨 앞 미리보기, review: 맨 뒤 복습, None: 사용안함)")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        # 미디어 경로 검증
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v
    
    @validator('study')
    def validate_study(cls, v):
        if v and v not in ["preview", "review"]:
            raise ValueError('study must be either "preview", "review", or None')
        return v