#!/usr/bin/env python3
"""
Video Clipping RESTful API
전문적인 비디오 클리핑 서비스 제공
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
import os
import json
import tempfile
import re
import logging
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import redis
import pickle

from ass_generator import ASSGenerator
from video_encoder import VideoEncoder

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="Video Clipping API",
    description="Professional video clipping service with subtitle support",
    version="1.0.0"
)

# CORS 설정 (운영 환경)
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Static files serving
app.mount("/static", StaticFiles(directory=".", html=True), name="static")

# Redis 연결 설정 (운영 환경용)
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        decode_responses=False  # pickle 사용을 위해
    )
    redis_client.ping()
    USE_REDIS = True
    logger.info("Redis connected successfully")
except:
    USE_REDIS = False
    logger.warning("Redis not available, using in-memory storage")
    redis_client = None

# 작업 상태 저장소 (Redis 사용 불가시 메모리)
job_status = {}

# 스레드풀 설정 (CPU 집약적 작업용)
executor = ThreadPoolExecutor(max_workers=int(os.getenv('MAX_WORKERS', 4)))

# 작업 만료 시간 (24시간)
JOB_EXPIRE_TIME = 86400

# 디렉토리 설정
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', 'output'))
OUTPUT_DIR.mkdir(exist_ok=True)

# 허용된 미디어 루트 디렉토리들 (보안)
ALLOWED_MEDIA_ROOTS = [
    Path('/mnt/qnap/media_eng/indexed_media'),
    Path('/mnt/qnap/media_kor'),
    Path(os.getenv('MEDIA_ROOT', '/media')),
    Path(__file__).parent / 'media',  # Local media directory for testing
]

# 환경 변수로 추가 경로 설정
if os.getenv('ADDITIONAL_MEDIA_ROOTS'):
    for root in os.getenv('ADDITIONAL_MEDIA_ROOTS').split(':'):
        ALLOWED_MEDIA_ROOTS.append(Path(root))

# 미디어 파일 관리
class MediaValidator:
    """미디어 파일 경로 검증"""
    
    @staticmethod
    def validate_media_path(media_path: str) -> Optional[Path]:
        """
        미디어 경로가 허용된 디렉토리 내에 있는지 확인
        """
        try:
            path = Path(media_path).resolve()
            
            # 파일 존재 확인
            if not path.exists() or not path.is_file():
                logger.warning(f"File not found: {media_path}")
                return None
            
            # 허용된 루트 디렉토리 내에 있는지 확인
            for allowed_root in ALLOWED_MEDIA_ROOTS:
                if allowed_root.exists():
                    try:
                        # 상대 경로 계산으로 확인
                        path.relative_to(allowed_root)
                        # 지원 형식 확인
                        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.flv'}
                        if path.suffix.lower() not in allowed_extensions:
                            logger.warning(f"Unsupported format: {path.suffix}")
                            return None
                        return path
                    except ValueError:
                        continue
            
            logger.warning(f"Path not in allowed directories: {media_path}")
            return None
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return None


class ClipData(BaseModel):
    """개별 클립 데이터"""
    start_time: float = Field(..., ge=0, description="시작 시간 (초)")
    end_time: float = Field(..., gt=0, description="종료 시간 (초)")
    text_eng: str = Field(..., description="영문 자막")
    text_kor: str = Field(..., description="한국어 번역")
    note: Optional[str] = Field("", description="문장 설명")
    keywords: Optional[List[str]] = Field([], description="핵심 키워드 리스트")
    text_eng_blank: Optional[str] = Field(None, description="키워드 블랭크 처리된 영문 (자동 생성 가능)")
    
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
    keywords: Optional[List[str]] = Field([], description="핵심 키워드 리스트")
    text_eng_blank: Optional[str] = Field(None, description="키워드 블랭크 처리된 영문 (자동 생성 가능)")
    clipping_type: int = Field(1, ge=1, le=2, description="클리핑 타입 (1 또는 2)")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")


class BatchClippingRequest(BaseModel):
    """배치 클리핑 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    clips: List[ClipData] = Field(..., description="클립 데이터 리스트")
    clipping_type: int = Field(1, ge=1, le=2, description="클리핑 타입 (1 또는 2)")
    individual_clips: bool = Field(False, description="개별 클립 저장 여부")
    
    @validator('media_path')
    def validate_media_path(cls, v):
        # 미디어 경로 검증
        validated_path = MediaValidator.validate_media_path(v)
        if not validated_path:
            raise ValueError(f'Invalid or unauthorized media path: {v}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "media_path": "/mnt/qnap/media_eng/indexed_media/sample.mp4",
                "start_time": 10.5,
                "end_time": 15.5,
                "text_eng": "Hello, how are you?",
                "text_kor": "안녕하세요, 어떻게 지내세요?",
                "note": "인사하기",
                "keywords": ["Hello", "how"],
                "clipping_type": 1,
                "individual_clips": False
            }
        }


class ClippingResponse(BaseModel):
    """클리핑 응답 모델"""
    job_id: str
    status: str
    message: str


class JobStatus(BaseModel):
    """작업 상태 모델"""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    message: str
    output_file: Optional[str] = None
    individual_clips: Optional[List[str]] = None
    error: Optional[str] = None


def generate_blank_text(text: str, keywords: List[str]) -> str:
    """키워드를 블랭크 처리"""
    if not keywords:
        return text
    
    blank_text = text
    for keyword in keywords:
        # 대소문자 구분 없이 찾되, 원본의 대소문자는 유지
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        blank_text = pattern.sub(lambda m: '_' * len(m.group()), blank_text)
    
    return blank_text


@app.get("/", tags=["Health"])
async def root():
    """웹 인터페이스 제공"""
    return FileResponse("index.html")

@app.get("/api", tags=["Health"])
async def api_info():
    """API 상태 확인"""
    return {
        "service": "Video Clipping API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/allowed-roots", tags=["Media"])
async def get_allowed_roots():
    """허용된 미디어 루트 디렉토리 목록"""
    return {
        "allowed_roots": [
            str(root) for root in ALLOWED_MEDIA_ROOTS if root.exists()
        ]
    }


@app.post("/api/clip", 
         response_model=ClippingResponse,
         tags=["Clipping"],
         summary="비디오 클립 생성 요청")
async def create_clip(
    request: ClippingRequest,
    background_tasks: BackgroundTasks
):
    """
    비디오 클립을 생성합니다.
    
    - **media_path**: 원본 비디오 파일 경로
    - **start_time**: 클립 시작 시간 (초)
    - **end_time**: 클립 종료 시간 (초)
    - **text_eng**: 영문 자막
    - **text_kor**: 한국어 자막
    - **note**: 설명 (선택)
    - **keywords**: 키워드 리스트 (선택)
    - **clipping_type**: 1 (기본) 또는 2 (키워드 블랭크)
    - **individual_clips**: 개별 클립 저장 여부
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # 작업 상태 초기화
    job_status[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "작업 대기 중...",
        "output_file": None,
        "individual_clips": None,
        "error": None
    }
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_clipping,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message="클리핑 작업이 시작되었습니다."
    )


async def process_clipping(job_id: str, request: ClippingRequest):
    """비디오 클리핑 처리"""
    try:
        # 작업 시작
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["progress"] = 10
        job_status[job_id]["message"] = "클리핑 준비 중..."
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 출력 디렉토리 생성
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 텍스트 블랭크 처리 (필요한 경우)
        text_eng_blank = request.text_eng_blank
        if request.clipping_type == 2 and not text_eng_blank:
            text_eng_blank = generate_blank_text(request.text_eng, request.keywords)
        
        # 자막 데이터 준비
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'english': request.text_eng,
            'korean': request.text_kor,
            'note': request.note,
            'eng': request.text_eng,  # 호환성
            'kor': request.text_kor   # 호환성
        }
        
        # ASS 파일 생성
        job_status[job_id]["progress"] = 30
        job_status[job_id]["message"] = "자막 파일 생성 중..."
        
        ass_generator = ASSGenerator()
        
        # Type 1: 기본 영한 자막
        if request.clipping_type == 1:
            ass_path = job_dir / "subtitle.ass"
            ass_generator.generate_ass([subtitle_data], str(ass_path))
        
        # Type 2: 블랭크 + 영한+노트
        else:
            # 블랭크 자막
            blank_subtitle = subtitle_data.copy()
            blank_subtitle['english'] = text_eng_blank
            blank_subtitle['eng'] = text_eng_blank
            blank_subtitle['korean'] = ''
            blank_subtitle['kor'] = ''
            blank_subtitle['note'] = ''
            
            blank_ass_path = job_dir / "subtitle_blank.ass"
            ass_generator.generate_ass([blank_subtitle], str(blank_ass_path))
            
            # 풀 자막 (영한 + 노트) - 키워드 강조 포함
            full_subtitle = subtitle_data.copy()
            full_subtitle['keywords'] = request.keywords  # 키워드 추가
            ass_path = job_dir / "subtitle_full.ass"
            ass_generator.generate_ass([full_subtitle], str(ass_path))
        
        # 비디오 클리핑
        job_status[job_id]["progress"] = 50
        job_status[job_id]["message"] = "비디오 클리핑 중..."
        
        video_encoder = VideoEncoder()
        output_path = job_dir / "output.mp4"
        
        # Type별 패턴 설정
        if request.clipping_type == 1:
            # Type 1: 무자막 2회 + 영한자막 2회
            video_encoder.pattern = {
                "no_subtitle": 2,
                "korean_with_note": 0,
                "both_subtitle": 2
            }
        else:
            # Type 2: 무자막 2회 + 블랭크 2회 + 영한자막+노트 2회
            # 커스텀 패턴이 필요하므로 직접 구현
            success = create_type2_clip(
                video_encoder,
                str(media_path),
                str(blank_ass_path),
                str(ass_path),
                str(output_path),
                request.start_time,
                request.end_time,
                request.individual_clips,
                job_dir
            )
        
        if request.clipping_type == 1:
            success = video_encoder.create_shadowing_video(
                media_path=str(media_path),
                ass_path=str(ass_path),
                output_path=str(output_path),
                start_time=request.start_time,
                end_time=request.end_time,
                padding_before=0.5,
                padding_after=0.5,
                subtitle_data=subtitle_data,
                save_individual_clips=request.individual_clips
            )
        
        if success:
            job_status[job_id]["progress"] = 90
            job_status[job_id]["message"] = "클리핑 완료, 파일 정리 중..."
            
            # 개별 클립 찾기
            individual_clips = []
            if request.individual_clips:
                clips_dir = job_dir.parent / "individual_clips"
                if clips_dir.exists():
                    for clip_file in clips_dir.glob("*.mp4"):
                        individual_clips.append(str(clip_file))
            
            # 메타데이터 저장
            metadata = {
                "job_id": job_id,
                "request": request.dict(),
                "output_file": str(output_path),
                "individual_clips": individual_clips,
                "created_at": datetime.now().isoformat()
            }
            
            with open(job_dir / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 작업 완료
            job_status[job_id]["status"] = "completed"
            job_status[job_id]["progress"] = 100
            job_status[job_id]["message"] = "클리핑 완료!"
            job_status[job_id]["output_file"] = str(output_path)
            job_status[job_id]["individual_clips"] = individual_clips
            
        else:
            raise Exception("비디오 클리핑 실패")
            
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"오류 발생: {str(e)}"


def create_type2_clip(encoder, media_path, blank_ass, full_ass, output_path, 
                     start_time, end_time, save_individual, job_dir):
    """Type 2 클리핑 생성 (무자막 + 블랭크 + 풀)"""
    temp_clips = []
    
    try:
        # 1. 무자막 2회
        for i in range(2):
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_clips.append(temp_file.name)
            temp_file.close()
            
            if not encoder._encode_clip(media_path, temp_clips[-1], 
                                       start_time, end_time - start_time, 
                                       subtitle_file=None):
                raise Exception(f"Failed to create no-subtitle clip {i+1}")
        
        # 2. 블랭크 자막 2회
        for i in range(2):
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_clips.append(temp_file.name)
            temp_file.close()
            
            if not encoder._encode_clip(media_path, temp_clips[-1], 
                                       start_time, end_time - start_time, 
                                       subtitle_file=blank_ass):
                raise Exception(f"Failed to create blank subtitle clip {i+1}")
        
        # 3. 풀 자막 2회
        for i in range(2):
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_clips.append(temp_file.name)
            temp_file.close()
            
            if not encoder._encode_clip(media_path, temp_clips[-1], 
                                       start_time, end_time - start_time, 
                                       subtitle_file=full_ass):
                raise Exception(f"Failed to create full subtitle clip {i+1}")
        
        # 개별 클립 저장
        if save_individual:
            individual_dir = job_dir / "individual_clips"
            individual_dir.mkdir(exist_ok=True)
            
            import shutil
            clip_names = ["no_sub_1", "no_sub_2", "blank_1", "blank_2", "full_1", "full_2"]
            for i, (clip_path, name) in enumerate(zip(temp_clips, clip_names)):
                dest = individual_dir / f"{name}.mp4"
                shutil.copy2(clip_path, str(dest))
        
        # 클립 연결
        if not encoder._concatenate_clips(temp_clips, output_path, gap_duration=1.5):
            raise Exception("Failed to concatenate clips")
        
        return True
        
    finally:
        # 임시 파일 정리
        for temp_clip in temp_clips:
            if os.path.exists(temp_clip):
                os.unlink(temp_clip)


@app.get("/api/status/{job_id}", 
         response_model=JobStatus,
         tags=["Status"],
         summary="작업 상태 확인")
async def get_job_status(job_id: str):
    """작업 상태를 확인합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(
        job_id=job_id,
        **job_status[job_id]
    )


@app.get("/api/download/{job_id}",
         tags=["Download"],
         summary="클립 다운로드")
async def download_clip(job_id: str):
    """생성된 클립을 다운로드합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    output_file = job_status[job_id]["output_file"]
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    
    return FileResponse(
        output_file,
        media_type="video/mp4",
        filename=f"clip_{job_id}.mp4"
    )


@app.get("/api/download/{job_id}/individual/{index}",
         tags=["Download"],
         summary="개별 클립 다운로드")
async def download_individual_clip(job_id: str, index: int):
    """개별 클립을 다운로드합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    individual_clips = job_status[job_id].get("individual_clips", [])
    if not individual_clips or index >= len(individual_clips):
        raise HTTPException(status_code=404, detail="Individual clip not found")
    
    clip_path = individual_clips[index]
    if not Path(clip_path).exists():
        raise HTTPException(status_code=404, detail="Clip file not found")
    
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"clip_{job_id}_individual_{index}.mp4"
    )


@app.post("/api/clip/batch",
         response_model=ClippingResponse,
         tags=["Clipping"],
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
        
        # 출력 디렉토리 생성
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(exist_ok=True)
        
        output_files = []
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
            
            # 텍스트 블랭크 처리
            text_eng_blank = clip_data.text_eng_blank
            if request.clipping_type == 2 and not text_eng_blank:
                text_eng_blank = generate_blank_text(clip_data.text_eng, clip_data.keywords)
            
            # 자막 데이터
            subtitle_data = {
                'start_time': 0,
                'end_time': clip_data.end_time - clip_data.start_time,
                'english': clip_data.text_eng,
                'korean': clip_data.text_kor,
                'note': clip_data.note,
                'eng': clip_data.text_eng,
                'kor': clip_data.text_kor
            }
            
            # ASS 파일 생성
            if request.clipping_type == 1:
                ass_path = clip_dir / "subtitle.ass"
                ass_generator.generate_ass([subtitle_data], str(ass_path))
            else:
                # 블랭크 자막
                blank_subtitle = subtitle_data.copy()
                blank_subtitle['english'] = text_eng_blank
                blank_subtitle['eng'] = text_eng_blank
                blank_subtitle['korean'] = ''
                blank_subtitle['kor'] = ''
                blank_subtitle['note'] = ''
                
                blank_ass_path = clip_dir / "subtitle_blank.ass"
                ass_generator.generate_ass([blank_subtitle], str(blank_ass_path))
                
                # 풀 자막 - 키워드 강조 포함
                full_subtitle = subtitle_data.copy()
                full_subtitle['keywords'] = clip_data.keywords  # 키워드 추가
                ass_path = clip_dir / "subtitle_full.ass"
                ass_generator.generate_ass([full_subtitle], str(ass_path))
            
            # 비디오 클리핑
            output_path = clip_dir / f"clip_{clip_num:03d}.mp4"
            
            # Type별 처리
            if request.clipping_type == 1:
                video_encoder.pattern = {
                    "no_subtitle": 2,
                    "korean_with_note": 0,
                    "both_subtitle": 2
                }
                success = video_encoder.create_shadowing_video(
                    media_path=str(media_path),
                    ass_path=str(ass_path),
                    output_path=str(output_path),
                    start_time=clip_data.start_time,
                    end_time=clip_data.end_time,
                    padding_before=0.5,
                    padding_after=0.5,
                    subtitle_data=subtitle_data,
                    save_individual_clips=request.individual_clips
                )
            else:
                success = create_type2_clip(
                    video_encoder,
                    str(media_path),
                    str(blank_ass_path),
                    str(ass_path),
                    str(output_path),
                    clip_data.start_time,
                    clip_data.end_time,
                    request.individual_clips,
                    clip_dir
                )
            
            if success:
                output_files.append({
                    "clip_num": clip_num,
                    "file": str(output_path),
                    "start_time": clip_data.start_time,
                    "end_time": clip_data.end_time,
                    "text_eng": clip_data.text_eng[:50] + "..."
                })
                job_status[job_id]["completed_clips"] = clip_num
            else:
                print(f"Warning: Failed to create clip {clip_num}")
        
        # 메타데이터 저장
        metadata = {
            "job_id": job_id,
            "media_path": str(media_path),
            "clipping_type": request.clipping_type,
            "total_clips": len(request.clips),
            "output_files": output_files,
            "created_at": datetime.now().isoformat()
        }
        
        with open(job_dir / "batch_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        job_status[job_id]["message"] = f"배치 클리핑 완료! ({len(output_files)}/{len(request.clips)}개 성공)"
        job_status[job_id]["output_files"] = output_files
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"배치 처리 오류: {str(e)}"


@app.get("/api/batch/status/{job_id}",
         tags=["Status"],
         summary="배치 작업 상태 확인")
async def get_batch_status(job_id: str):
    """배치 작업 상태를 확인합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]


@app.get("/api/batch/download/{job_id}/{clip_num}",
         tags=["Download"],
         summary="배치 클립 개별 다운로드")
async def download_batch_clip(job_id: str, clip_num: int):
    """배치 작업의 특정 클립을 다운로드합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    clip_path = OUTPUT_DIR / job_id / f"clip_{clip_num:03d}" / f"clip_{clip_num:03d}.mp4"
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"batch_{job_id}_clip_{clip_num:03d}.mp4"
    )


@app.delete("/api/job/{job_id}",
            tags=["Management"],
            summary="작업 삭제")
async def delete_job(job_id: str):
    """작업과 관련 파일을 삭제합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 파일 삭제
    job_dir = OUTPUT_DIR / job_id
    if job_dir.exists():
        import shutil
        shutil.rmtree(job_dir)
    
    # 상태 삭제
    del job_status[job_id]
    
    return {"message": "Job deleted successfully"}


# 정리 작업 (만료된 작업 제거)
async def cleanup_expired_jobs():
    """만료된 작업 정리"""
    while True:
        try:
            current_time = datetime.now()
            expired_jobs = []
            
            for job_id, status in job_status.items():
                # 생성 시간 확인 (메타데이터에서)
                metadata_path = OUTPUT_DIR / job_id / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        created_at = datetime.fromisoformat(metadata.get('created_at', current_time.isoformat()))
                        
                        # 24시간 경과 확인
                        if (current_time - created_at).total_seconds() > JOB_EXPIRE_TIME:
                            expired_jobs.append(job_id)
            
            # 만료된 작업 제거
            for job_id in expired_jobs:
                try:
                    # 파일 삭제
                    job_dir = OUTPUT_DIR / job_id
                    if job_dir.exists():
                        import shutil
                        shutil.rmtree(job_dir)
                    
                    # 상태 삭제
                    if job_id in job_status:
                        del job_status[job_id]
                    
                    logger.info(f"Cleaned up expired job: {job_id}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up job {job_id}: {e}")
            
            # 1시간마다 실행
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            await asyncio.sleep(300)  # 오류 시 5분 후 재시도


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 이벤트"""
    # 정리 작업 시작
    asyncio.create_task(cleanup_expired_jobs())
    logger.info("Video Clipping API started")


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 이벤트"""
    # 스레드풀 종료
    executor.shutdown(wait=True)
    logger.info("Video Clipping API shutdown")


if __name__ == "__main__":
    import uvicorn
    
    # 운영 환경 설정
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_config["formatters"]["access"]["fmt"] = '%(asctime)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8080)),
        workers=int(os.getenv("WORKERS", 1)),
        log_config=log_config,
        access_log=True
    )