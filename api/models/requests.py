"""
API Request Models
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from .validators import MediaValidator


class ClipData(BaseModel):
    """개별 클립 데이터"""
    start_time: float = Field(..., ge=0, description="시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="종료 시간 (초)")
    text_eng: str = Field(..., description="영문 자막")
    text_kor: str = Field(..., description="한국어 번역")
    note: Optional[str] = Field("", description="문장 설명")
    keywords: Optional[List[str]] = Field([], description="핵심 키워드 리스트 (Type 2에서 사용)")
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v


class ClippingRequest(BaseModel):
    """클리핑 요청 모델 (단일 클립)"""
    media_path: str = Field(..., description="미디어 파일 경로")
    start_time: float = Field(..., ge=0, description="시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="종료 시간 (초)")
    text_eng: str = Field(..., description="영문 자막")
    text_kor: str = Field(..., description="한국어 번역")
    note: Optional[str] = Field("", description="문장 설명")
    keywords: Optional[List[str]] = Field([], description="핵심 키워드 리스트 (Type 2에서 사용)")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호 (1-3: 일반, 11-13: 쇼츠, 21-29: TTS, 31-39: 스터디클립, 91+: 교재)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")


class BatchClippingRequest(BaseModel):
    """배치 클리핑 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    clips: List[ClipData] = Field(..., description="클립 데이터 리스트")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호 (1-3: 일반, 11-13: 쇼츠, 21-29: TTS, 31-39: 스터디클립, 91+: 교재)")
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
        if v is not None and v not in ['preview', 'review']:
            raise ValueError(f'study must be "preview", "review", or null/none, got: {v}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "media_path": "/mnt/qnap/media_eng/indexed_media/sample.mp4",
                "start_time": 10.5,
                "end_time": 15.5,
                "text_eng": "Hello, how are you?",
                "text_kor": "안녕하세요, 어떻게 지내세요?",
                "note": "인사하기",
                "keywords": ["Hello", "how"],
                "template_number": 1,
                "individual_clips": False
            }
        }


class SubtitleSegment(BaseModel):
    """자막 세그먼트 모델"""
    start_time: float = Field(..., gt=0, description="시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="종료 시간 (초)")
    text_eng: str = Field(..., description="영문 자막")
    text_kor: str = Field(..., description="한국어 번역")
    is_bookmarked: bool = Field(False, description="북마크 여부")
    note: Optional[str] = Field("", description="문장 설명")
    
    @validator('end_time')
    def validate_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v


class TextbookLessonRequest(BaseModel):
    """교재형 학습 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    subtitle_segments: List[SubtitleSegment] = Field(..., description="전체 자막 세그먼트")
    lesson_title: str = Field("Today's Expressions", description="레슨 제목")
    template_number: int = Field(91, ge=91, le=93, description="템플릿 번호 (91: 기본)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "media_path": "/mnt/qnap/media_eng/indexed_media/sample.mp4",
                "subtitle_segments": [
                    {
                        "start_time": 0.5,
                        "end_time": 3.5,
                        "text_eng": "Hello everyone",
                        "text_kor": "안녕하세요 여러분",
                        "is_bookmarked": False
                    },
                    {
                        "start_time": 10.5,
                        "end_time": 15.5,
                        "text_eng": "I've been waiting for you",
                        "text_kor": "널 기다리고 있었어",
                        "is_bookmarked": True,
                        "note": "현재완료진행형"
                    },
                    {
                        "start_time": 20.0,
                        "end_time": 23.0,
                        "text_eng": "Thank you",
                        "text_kor": "감사합니다",
                        "is_bookmarked": False
                    }
                ],
                "lesson_title": "Present Perfect Continuous",
                "template_number": 91
            }
        }