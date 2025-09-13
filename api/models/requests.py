"""
Request Models for Video Clipping API
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from .validators import MediaValidator


class ClipData(BaseModel):
    """개별 클립 데이터"""
    media_path: Optional[str] = Field(None, description="개별 미디어 경로 (다중 미디어 모드에서 사용)")
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
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        # 미디어 경로 검증
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v


class BatchClippingRequest(BaseModel):
    """배치 클리핑 요청 모델"""
    media_path: Optional[str] = Field(None, description="미디어 파일 경로 (단일 미디어 모드)")
    clips: List[ClipData] = Field(..., description="클립 데이터 리스트")
    template_number: int = Field(1, ge=1, le=100, description="템플릿 번호 (1-3: 일반, 11-13: 쇼츠, 21-29: TTS, 31-39: 스터디클립)")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    title_1: Optional[str] = Field(None, description="타이틀 첫 번째 줄 (쇼츠: 흰색 120pt, 일반: 왼쪽 흰색 40pt)")
    title_2: Optional[str] = Field(None, description="타이틀 두 번째 줄 (쇼츠: 골드 90pt, 일반: 오른쪽 흰색 40pt)")
    title_3: Optional[str] = Field(None, description="타이틀 세 번째 줄 (쇼츠 템플릿 2,3용: 흰색 60pt, \\n 지원)")
    study: Optional[str] = Field(None, description="학습 모드 (preview: 맨 앞 미리보기, review: 맨 뒤 복습, None: 사용안함)")
    include_intro: bool = Field(False, description="인트로 포함 여부")
    intro_header_text: Optional[str] = Field(None, description="인트로 영어 헤더 텍스트")
    intro_korean_text: Optional[str] = Field(None, description="인트로 한국어 텍스트")
    intro_explanation: Optional[str] = Field(None, description="인트로 설명 텍스트")
    intro_use_blur: bool = Field(True, description="인트로 배경 흐림 효과")
    intro_use_gradient: bool = Field(False, description="인트로 그라데이션 효과")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        if v is None:
            return v
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
    
    @validator('clips')
    def validate_clips(cls, v, values):
        """클립 검증 - 단일 미디어 모드와 다중 미디어 모드 확인"""
        media_path = values.get('media_path')
        
        for clip in v:
            if media_path is None and clip.media_path is None:
                raise ValueError('미디어 경로가 지정되지 않았습니다. media_path 또는 각 클립의 media_path를 지정해주세요.')
            
            # 다중 미디어 모드에서 각 클립의 미디어 경로 검증
            if clip.media_path:
                validated = MediaValidator.validate_media_path(clip.media_path)
                if not validated:
                    raise ValueError(f'Invalid or unauthorized media path: {clip.media_path}')
        
        return v


class SubtitleInfo(BaseModel):
    """자막 정보"""
    start: float = Field(..., description="자막 시작 시간")
    end: float = Field(..., description="자막 종료 시간")
    eng: str = Field(..., description="영어 자막")
    kor: str = Field(..., description="한글 자막")


class MixedTemplateClipData(BaseModel):
    """개별 템플릿을 지정할 수 있는 클립 데이터"""
    start_time: float = Field(..., ge=0, description="클립 시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="클립 종료 시간 (초)")
    template_number: int = Field(..., ge=0, le=100, description="템플릿 번호 (0: 구간추출, 1-100: 학습)")
    
    # template 0 (구간 추출)일 때 사용
    subtitles: Optional[List[SubtitleInfo]] = Field(None, description="구간 내 자막들 (template 0)")
    
    # template 1-100 (학습)일 때 사용
    text_eng: Optional[str] = Field(None, description="영문 자막 (template 1-100)")
    text_kor: Optional[str] = Field(None, description="한글 자막 (template 1-100)")
    note: Optional[str] = Field(None, description="메모")
    keywords: Optional[List[str]] = Field(None, description="키워드 리스트 (템플릿 2번용)")
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v
    
    @validator('subtitles', always=True)
    def validate_data_consistency(cls, v, values):
        template_num = values.get('template_number')
        
        if template_num == 0:
            # template 0은 subtitles 필수
            if not v:
                raise ValueError('subtitles is required for template 0')
        
        return v
    
    @validator('text_eng', always=True)
    def validate_text_fields(cls, v, values):
        template_num = values.get('template_number')
        
        # template 1-100은 text_eng 또는 text_kor 중 하나는 필수
        if template_num and template_num > 0:
            if not v and not values.get('text_kor'):
                raise ValueError('text_eng or text_kor is required for template 1-100')
        
        return v


class MixedTemplateRequest(BaseModel):
    """혼합 템플릿 클리핑 요청"""
    media_path: str = Field(..., description="미디어 파일 경로")
    clips: List[MixedTemplateClipData] = Field(..., description="각각 다른 템플릿이 적용될 클립들")
    combine: bool = Field(True, description="True: 하나의 비디오로 결합, False: 개별 파일로 생성")
    title_1: Optional[str] = Field(None, description="결합 비디오 타이틀 첫 번째 줄")
    title_2: Optional[str] = Field(None, description="결합 비디오 타이틀 두 번째 줄")
    transitions: bool = Field(False, description="트랜지션 효과 사용 여부")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v


class ExtractRangeRequest(BaseModel):
    """구간 추출 요청 - 여러 자막을 포함한 긴 구간"""
    media_path: str = Field(..., description="미디어 파일 경로")
    start_time: float = Field(..., ge=0, description="전체 구간 시작 시간")
    end_time: float = Field(..., gt=0, description="전체 구간 종료 시간")
    subtitles: List[SubtitleInfo] = Field(..., description="구간 내 자막들의 타이밍 정보")
    template_number: int = Field(0, description="템플릿 번호 (0: 원본 스타일)")
    title_1: Optional[str] = Field(None, description="타이틀 첫 번째 줄")
    title_2: Optional[str] = Field(None, description="타이틀 두 번째 줄")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v