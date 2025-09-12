#!/usr/bin/env python3
"""
Video Clipping RESTful API
전문적인 비디오 클리핑 서비스 제공
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
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
import signal
import psutil
import subprocess

from ass_generator import ASSGenerator
from video_encoder import VideoEncoder
from template_video_encoder import TemplateVideoEncoder
from subtitle_generator import SubtitleGenerator
from database import (
    init_db, save_job_to_db, update_job_status, get_job_by_id,
    get_recent_jobs, search_jobs, get_statistics, delete_job,
    delete_jobs_bulk, cleanup_old_jobs, get_disk_usage
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        logging.FileHandler('logs/clipping_api.log', mode='a')  # 파일 출력
    ],
    force=True  # 기존 핸들러 강제 재설정
)

# 다른 모듈의 로거도 설정
logging.getLogger('template_video_encoder').setLevel(logging.INFO)
logging.getLogger('video_encoder').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Rate limiter 초기화
limiter = Limiter(key_func=get_remote_address)

# FastAPI 앱 초기화
app = FastAPI(
    title="Video Clipping API",
    description="Professional video clipping service with subtitle support",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Validation 에러 핸들러 추가
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    logger.error(f"Request body: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body)
        }
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

# Serve frontend files
from fastapi.staticfiles import StaticFiles
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/admin", StaticFiles(directory=".", html=True), name="admin")

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
except (redis.ConnectionError, redis.TimeoutError) as e:
    USE_REDIS = False
    logger.warning(f"Redis not available: {e}, using in-memory storage")
    redis_client = None

# 작업 상태 저장소 (Redis 사용 불가시 메모리)
job_status = {}
# 메모리 사용량 제한을 위한 최대 작업 수
MAX_JOB_MEMORY = 1000

# 실행 중인 프로세스 추적
active_processes = {}

# 스레드풀 설정 (CPU 집약적 작업용)
executor = ThreadPoolExecutor(max_workers=int(os.getenv('MAX_WORKERS', 4)))

# 작업 만료 시간 (24시간)
JOB_EXPIRE_TIME = 86400

def cleanup_memory_jobs():
    """메모리에 저장된 오래된 작업 정리"""
    if not USE_REDIS and len(job_status) > MAX_JOB_MEMORY:
        # 가장 오래된 완료된 작업들 제거
        completed_jobs = [(k, v) for k, v in job_status.items() 
                         if v.get('status') in ['completed', 'failed']]
        if completed_jobs:
            # 시간순 정렬 (오래된 것부터)
            completed_jobs.sort(key=lambda x: x[1].get('created_at', ''))
            # 50% 제거
            for job_id, _ in completed_jobs[:len(completed_jobs)//2]:
                del job_status[job_id]
                logger.info(f"Removed old job from memory: {job_id}")

def cleanup_job_processes(job_id: str):
    """작업과 관련된 모든 프로세스 정리"""
    if job_id in active_processes:
        process_info = active_processes[job_id]
        try:
            # 메인 프로세스 종료
            parent = psutil.Process(process_info['pid'])
            
            # 자식 프로세스들도 모두 종료
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            # 잠시 대기 후 강제 종료
            gone, alive = psutil.wait_procs(children, timeout=5)
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
                    
            # 메인 프로세스 종료
            try:
                parent.terminate()
                parent.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except Exception as e:
            logger.error(f"Error cleaning up processes for job {job_id}: {e}")
        finally:
            # 추적 목록에서 제거
            del active_processes[job_id]

def update_job_status_both(job_id: str, status: str, progress: int = None, 
                          message: str = None, output_file: str = None, error_message: str = None):
    """메모리와 데이터베이스 동시 업데이트 (multi-worker 지원)"""
    # 메모리 업데이트 (현재 worker)
    if job_id in job_status:
        job_status[job_id]["status"] = status
        if progress is not None:
            job_status[job_id]["progress"] = progress
        if message:
            job_status[job_id]["message"] = message
        if output_file:
            job_status[job_id]["output_file"] = output_file
        if error_message:
            job_status[job_id]["error_message"] = error_message
    
    # 데이터베이스 업데이트 (모든 worker가 공유)
    update_job_status(job_id, status, progress, output_file, error_message, message)

# 디렉토리 설정
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', str(BASE_DIR / 'output')))
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
    """키워드를 블랭크 처리 (띄어쓰기 유지)"""
    if not keywords:
        return text
    
    blank_text = text
    for keyword in keywords:
        # 대소문자 구분 없이 찾되, 원본의 대소문자는 유지
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        # 띄어쓰기는 그대로 유지하면서 문자만 _ 로 대체
        def replace_with_blanks(match):
            matched_text = match.group()
            # 각 문자를 확인하여 공백은 유지, 문자는 _로 대체
            return ''.join('_' if char != ' ' else ' ' for char in matched_text)
        
        blank_text = pattern.sub(replace_with_blanks, blank_text)
    
    return blank_text


@app.get("/", tags=["Health"])
async def root():
    """웹 인터페이스 제공"""
    return FileResponse("index.html")

@app.get("/admin", response_class=FileResponse, tags=["Admin"])
async def admin_page():
    """관리자 페이지"""
    return FileResponse("admin.html")

@app.get("/restful", response_class=HTMLResponse, include_in_schema=False)
async def restful_docs():
    """RESTful API 문서 페이지"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RESTful API Documentation</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; }
            .endpoint { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .method { display: inline-block; padding: 5px 15px; color: white; font-weight: bold; border-radius: 4px; }
            .post { background: #28a745; }
            .get { background: #17a2b8; }
            .delete { background: #dc3545; }
            pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }
            code { font-family: monospace; }
            .nav { margin-bottom: 30px; }
            .nav a { margin-right: 20px; text-decoration: none; color: #007bff; }
            .nav a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RESTful API Documentation</h1>
            <div class="nav">
                <a href="/">← 홈으로</a>
                <a href="/docs">Swagger UI</a>
                <a href="/redoc">ReDoc</a>
                <a href="/admin">관리자</a>
            </div>
            
            <div class="endpoint">
                <h2>클리핑 타입 설명</h2>
                <h3>Type 1: 기본 패턴</h3>
                <ul>
                    <li>무자막 × 2회</li>
                    <li>영한자막 × 2회</li>
                </ul>
                
                <h3>Type 2: 확장 패턴 (키워드 하이라이트)</h3>
                <ul>
                    <li>무자막 × 2회</li>
                    <li>키워드 블랭크 × 2회</li>
                    <li>영한자막+노트 × 2회 (키워드 강조)</li>
                </ul>
            </div>
            
            <div class="endpoint">
                <h2><span class="method post">POST</span> /api/clip</h2>
                <p>단일 비디오 클립을 생성합니다.</p>
                <h3>Request Body</h3>
                <pre><code>{
  "media_path": "/mnt/qnap/media_eng/indexed_media/sample.mp4",
  "start_time": 10.5,
  "end_time": 15.5,
  "text_eng": "Hello, how are you?",
  "text_kor": "안녕하세요, 어떻게 지내세요?",
  "note": "인사하기",
  "keywords": ["Hello", "how"],
  "template_number": 1,
  "individual_clips": false
}</code></pre>
                <h3>Response</h3>
                <pre><code>{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "accepted",
  "message": "클리핑 작업이 시작되었습니다."
}</code></pre>
            </div>
            
            <div class="endpoint">
                <h2><span class="method get">GET</span> /api/status/{job_id}</h2>
                <p>작업 상태를 확인합니다.</p>
                <h3>Response</h3>
                <pre><code>{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "progress": 100,
  "message": "클리핑 완료!",
  "output_file": "output/123e4567/output.mp4",
  "individual_clips": null,
  "error": null
}</code></pre>
            </div>
            
            <div class="endpoint">
                <h2><span class="method get">GET</span> /api/download/{job_id}</h2>
                <p>생성된 클립을 다운로드합니다.</p>
            </div>
            
            <div class="endpoint">
                <h2><span class="method post">POST</span> /api/clip/batch</h2>
                <p>여러 개의 비디오 클립을 한 번에 생성합니다.</p>
                <h3>Request Body</h3>
                <pre><code>{
  "media_path": "/mnt/qnap/media_eng/indexed_media/sample.mp4",
  "clips": [
    {
      "start_time": 10.5,
      "end_time": 15.5,
      "text_eng": "Hello, how are you?",
      "text_kor": "안녕하세요, 어떻게 지내세요?",
      "note": "인사하기",
      "keywords": ["Hello", "how"]
    }
  ],
  "template_number": 1,
  "individual_clips": false
}</code></pre>
            </div>
            
            <div class="endpoint">
                <h2><span class="method delete">DELETE</span> /api/job/{job_id}</h2>
                <p>작업과 관련 파일을 삭제합니다.</p>
            </div>
        </div>
    </body>
    </html>
    """

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
    - **template_number**: 1 (기본), 2 (키워드 블랭크), 또는 3 (점진적 학습)
    - **individual_clips**: 개별 클립 저장 여부
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # Debug logging
    logger.info(f"[Job {job_id}] Single clip request - Type: {request.template_number}, Keywords: {request.keywords}")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "작업 대기 중...",
        "output_file": None,
        "individual_clips": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "text_eng": request.text_eng,
        "text_kor": request.text_kor,
        "note": request.note,
        "keywords": request.keywords
    }
    job_status[job_id] = job_data
    
    # DB에 저장
    try:
        save_job_to_db(job_id, job_data)
    except Exception as e:
        logger.error(f"Failed to save job to DB: {e}")
    
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
    
    # Template 91 특별 처리 추가
    if request.template_number == 91:
        logger.info(f"Template 91 detected, redirecting to template_91 processing")
        
        # template_91은 apply_template 방식을 사용해야 함
        return await _process_template_91_single_clip(job_id, request)
    
    try:
        # 작업 시작 (메모리와 DB 동시 업데이트)
        update_job_status_both(job_id, "processing", 10, message="클리핑 준비 중...")
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 날짜별 디렉토리 구조: /output/YYYY-MM-DD/job_id
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 텍스트 블랭크 처리 (Type 2, 3인 경우 자동 생성)
        text_eng_blank = None
        if request.template_number in [2, 3]:
            text_eng_blank = generate_blank_text(request.text_eng, request.keywords)
        
        # 쇼츠용 줄바꿈 처리 함수
        def add_line_breaks(text: str, max_chars: int = 20) -> str:
            """긴 텍스트에 줄바꿈 추가"""
            if not text or len(text) <= max_chars:
                return text
            
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
                    current_line.append(word)
                    current_length += word_length
            
            if current_line:
                lines.append(' '.join(current_line))
            
            return '\\n'.join(lines)
        
        # 자막 데이터 준비
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'english': request.text_eng,
            'korean': request.text_kor,
            'note': request.note,
            'eng': request.text_eng,  # 호환성
            'kor': request.text_kor,   # 호환성
            'eng_text_l': request.text_eng,  # Long version (일반)
            'eng_text_s': add_line_breaks(request.text_eng, 20),  # Short version (쇼츠)
            'kor_text_l': request.text_kor,  # Long version (일반)
            'kor_text_s': add_line_breaks(request.text_kor, 15),  # Short version (쇼츠)
            'keywords': request.keywords,  # Type 2를 위한 키워드
            'template_number': request.template_number,  # 클리핑 타입 전달
            'text_eng_blank': text_eng_blank  # Type 2를 위한 blank 텍스트
        }
        
        # 자막 파일 생성은 템플릿 인코더가 자동으로 처리
        update_job_status_both(job_id, "processing", 30, message="자막 파일 생성 중...")
        
        # 비디오 클리핑 - 템플릿 기반 접근
        update_job_status_both(job_id, "processing", 50, message="비디오 클리핑 중...")
        
        # 템플릿 기반 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # 날짜시간_tp_X.mp4 형식의 파일명 생성
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_tp_{request.template_number}.mp4"
        output_path = job_dir / filename
        
        # 템플릿 이름 결정 (11, 12, 13은 쇼츠 버전으로 매핑)
        template_mapping = {
            11: "template_1_shorts",
            12: "template_2_shorts", 
            13: "template_3_shorts",
            21: "template_tts",  # TTS 해설 템플릿 1
            22: "template_tts",  # TTS 해설 템플릿 2
            23: "template_tts",  # TTS 해설 템플릿 3
            31: "template_study_preview",  # 스터디 클립 - 미리보기
            32: "template_study_review",   # 스터디 클립 - 복습
            33: "template_study_shorts_preview",  # 쇼츠 스터디 클립 - 미리보기
            34: "template_study_shorts_review",   # 쇼츠 스터디 클립 - 복습
            35: "template_study_original", # 스터디 클립 - 원본 오디오
            36: "template_study_shorts_original", # 쇼츠 스터디 클립 - 원본 오디오
            91: "template_91"    # 교재형 학습 템플릿
        }
        
        if request.template_number in template_mapping:
            template_name = template_mapping[request.template_number]
        else:
            template_name = f"template_{request.template_number}"
        
        # 템플릿을 사용하여 비디오 생성
        success = template_encoder.create_from_template(
            template_name=template_name,
            media_path=str(media_path),
            subtitle_data=subtitle_data,
            output_path=str(output_path),
            start_time=request.start_time,
            end_time=request.end_time,
            padding_before=0.5,
            padding_after=0.5,
            save_individual_clips=request.individual_clips
        )
        
        if success:
            update_job_status_both(job_id, "processing", 90, message="클리핑 완료, 파일 정리 중...")
            
            # 개별 클립 찾기
            individual_clips = []
            if request.individual_clips:
                clips_dir = job_dir / "individual_clips"
                if clips_dir.exists():
                    for clip_file in clips_dir.glob("**/*.mp4"):
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
            job_status[job_id]["individual_clips"] = individual_clips
            
            # 완료 상태 업데이트 (메모리와 DB 동시)
            update_job_status_both(job_id, "completed", 100, message="클리핑 완료!", output_file=str(output_path))
            
        else:
            raise Exception("비디오 클리핑 실패")
            
    except Exception as e:
        job_status[job_id]["error"] = str(e)
        
        # 실패 상태 업데이트 (메모리와 DB 동시)
        update_job_status_both(job_id, "failed", message=f"오류 발생: {str(e)}", error_message=str(e))


# create_type2_clip 함수는 템플릿 기반 접근으로 대체됨


@app.get("/api/status/{job_id}", 
         response_model=JobStatus,
         tags=["Status"],
         summary="작업 상태 확인")
async def get_job_status(job_id: str):
    """작업 상태를 확인합니다."""
    # Check memory first (current worker)
    if job_id in job_status:
        return JobStatus(
            job_id=job_id,
            **job_status[job_id]
        )
    
    # If not in memory, check database (for multi-worker support)
    db_job = get_job_by_id(job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert database job to status format
    status_data = {
        "status": db_job.status,
        "progress": db_job.progress,
        "message": db_job.message or "Processing...",
        "output_file": db_job.output_file,
        "created_at": db_job.created_at.isoformat() if db_job.created_at else None
    }
    
    return JobStatus(
        job_id=job_id,
        **status_data
    )


@app.get("/api/download/{job_id}",
         tags=["Download"],
         summary="클립 다운로드")
async def download_clip(job_id: str):
    """생성된 클립을 다운로드합니다."""
    # Check memory first (current worker)
    output_file = None
    status = None
    
    if job_id in job_status:
        status = job_status[job_id]["status"]
        output_file = job_status[job_id]["output_file"]
    else:
        # Check database (for multi-worker support)
        db_job = get_job_by_id(job_id)
        if not db_job:
            raise HTTPException(status_code=404, detail="Job not found")
        status = db_job.status
        output_file = db_job.output_file
    
    if status != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
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


@app.get("/api/video/{job_id}",
         tags=["Video"],
         summary="비디오 스트리밍")
async def stream_video(job_id: str, request: Request):
    """생성된 비디오를 스트리밍합니다."""
    # Check for video file
    output_file = None
    
    if job_id in job_status:
        output_file = job_status[job_id]["output_file"]
    else:
        # Check database
        db_job = get_job_by_id(job_id)
        if db_job and db_job.output_file:
            output_file = db_job.output_file
    
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get file size
    file_size = os.path.getsize(output_file)
    
    # Handle range requests for video streaming
    range_header = request.headers.get('range')
    
    if range_header:
        # Parse range header
        range_match = range_header.replace('bytes=', '').split('-')
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1
        
        # Read the requested chunk
        chunk_size = end - start + 1
        
        def generate():
            with open(output_file, 'rb') as video:
                video.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = video.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        return StreamingResponse(
            generate(),
            status_code=206,
            headers={
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(chunk_size),
                'Content-Type': 'video/mp4',
            }
        )
    else:
        # Return entire file
        def generate():
            with open(output_file, 'rb') as video:
                while True:
                    chunk = video.read(8192)
                    if not chunk:
                        break
                    yield chunk
        
        return StreamingResponse(
            generate(),
            media_type='video/mp4',
            headers={
                'Content-Length': str(file_size),
                'Accept-Ranges': 'bytes',
            }
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
    
    # Debug logging
    logger.info(f"[Job {job_id}] Batch request - Type: {request.template_number}, Clips: {len(request.clips)}")
    if request.title_1 or request.title_2:
        logger.info(f"[Job {job_id}] Titles - title_1: '{request.title_1}', title_2: '{request.title_2}'")
    else:
        logger.info(f"[Job {job_id}] No titles provided")
    for i, clip in enumerate(request.clips):
        logger.info(f"  Clip {i+1}: Keywords: {clip.keywords}")
    
    # 메모리 정리
    cleanup_memory_jobs()
    
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


@app.post("/api/clip/textbook",
         response_model=ClippingResponse,
         tags=["Clipping"],
         summary="교재형 학습 비디오 생성")
async def create_textbook_lesson(
    request: TextbookLessonRequest,
    background_tasks: BackgroundTasks
):
    """
    5개의 북마크를 활용하여 영어 교재형 학습 비디오를 생성합니다.
    
    구성:
    - Warmup: 오늘의 표현 소개
    - Expression 학습: 각 표현별 소개, 원본, 분석, 연습
    - Pattern Focus: 공통 패턴 분석
    - Review: 복습 퀴즈
    - Wrap-up: 마무리
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # 북마크된 세그먼트 개수 계산
    bookmarked_count = sum(1 for seg in request.subtitle_segments if seg.is_bookmarked)
    logger.info(f"[Job {job_id}] Textbook lesson request - {bookmarked_count} bookmarks")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "교재형 학습 준비 중...",
        "output_file": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "subtitle_segments": [s.dict() for s in request.subtitle_segments],
        "lesson_title": request.lesson_title
    }
    job_status[job_id] = job_data
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_textbook_lesson,
        job_id,
        request
    )
    
    return ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"교재형 학습 비디오 생성이 시작되었습니다. ({bookmarked_count}개 북마크)"
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
        
        # 날짜별 디렉토리 구조: /output/YYYY-MM-DD/job_id
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        output_files = []
        review_clip_path = None
        
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
            from review_clip_generator import ReviewClipGenerator
            review_generator = ReviewClipGenerator()
            
            try:
                # 모드에 따른 타이틀 텍스트 결정
                review_title = "스피드 미리보기" if request.study == "preview" else "스피드 복습"
                
                success = await review_generator.create_review_clip(
                    clips_data=clips_data_for_review,
                    output_path=str(review_clip_path),
                    title=review_title,
                    template_number=request.template_number,
                    video_path=request.video_path,
                    clip_timestamps=clip_timestamps
                )
                
                if success and review_clip_path.exists():
                    logger.info(f"Review clip created: {review_clip_path}")
                    # 리뷰 클립을 임시 저장 (나중에 위치에 따라 추가)
                    job_status[job_id]["review_clip_data"] = {
                        "type": "study",
                        "file": str(review_clip_path),
                        "description": f"{review_title} 클립"
                    }
                else:
                    logger.warning("Failed to create review clip, continuing without it")
                    review_clip_path = None
                    
            except Exception as e:
                logger.error(f"Review clip creation error: {e}")
                # 리뷰 클립 실패해도 계속 진행
                review_clip_path = None
        
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
            
            # 텍스트 블랭크 처리 (Type 2, 3인 경우 자동 생성)
            text_eng_blank = None
            if request.template_number in [2, 3]:
                text_eng_blank = generate_blank_text(clip_data.text_eng, clip_data.keywords)
            
            # 쇼츠용 줄바꿈 처리 함수
            def add_line_breaks(text: str, max_chars: int = 20) -> str:
                """긴 텍스트에 줄바꿈 추가"""
                if not text or len(text) <= max_chars:
                    return text
                
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
            
            # 자막 데이터
            subtitle_data = {
                'start_time': 0,
                'end_time': clip_data.end_time - clip_data.start_time,
                'english': clip_data.text_eng,
                'korean': clip_data.text_kor,
                'note': clip_data.note,
                'eng': clip_data.text_eng,
                'kor': clip_data.text_kor,
                'eng_text_l': clip_data.text_eng,  # Long version (일반)
                'eng_text_s': add_line_breaks(clip_data.text_eng, 20),  # Short version (쇼츠)
                'kor_text_l': clip_data.text_kor,  # Long version (일반)
                'kor_text_s': add_line_breaks(clip_data.text_kor, 15),  # Short version (쇼츠)
                'keywords': clip_data.keywords,  # Type 2를 위한 키워드
                'template_number': request.template_number,  # 클리핑 타입 전달
                'text_eng_blank': text_eng_blank,  # Type 2를 위한 blank 텍스트
                'title_1': request.title_1,  # 배치 전체 타이틀 첫 번째 줄
                'title_2': request.title_2,  # 배치 전체 타이틀 두 번째 줄
                'title_3': request.title_3   # 배치 전체 타이틀 세 번째 줄 (설명용)
            }
            
            # 비디오 클리핑 - 템플릿 기반 (자막 파일 자동 생성)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_tp_{request.template_number}_c{clip_num:03d}.mp4"
            output_path = clip_dir / filename
            
            # 템플릿 기반 인코더 사용
            template_encoder = TemplateVideoEncoder()
            
            # 템플릿 이름 결정 (11, 12, 13은 쇼츠 버전으로 매핑)
            template_mapping = {
                11: "template_1_shorts",
                12: "template_2_shorts", 
                13: "template_3_shorts",
                21: "template_tts",  # TTS 해설 템플릿 1
                22: "template_tts",  # TTS 해설 템플릿 2
                23: "template_tts",  # TTS 해설 템플릿 3
                31: "template_study_preview",  # 스터디 클립 - 미리보기
                32: "template_study_review",   # 스터디 클립 - 복습
                33: "template_study_shorts_preview",  # 쇼츠 스터디 클립 - 미리보기
                34: "template_study_shorts_review",   # 쇼츠 스터디 클립 - 복습
                35: "template_study_original", # 스터디 클립 - 원본 오디오
                36: "template_study_shorts_original" # 쇼츠 스터디 클립 - 원본 오디오
            }
            
            if request.template_number in template_mapping:
                template_name = template_mapping[request.template_number]
            else:
                template_name = f"template_{request.template_number}"
            
            # 템플릿 91-93은 apply_template 방식 사용
            if request.template_number in [91, 92, 93]:
                # 세그먼트 형식으로 변환
                segment = {
                    "start_time": clip_data.start_time,
                    "end_time": clip_data.end_time,
                    "text_eng": clip_data.text_eng,
                    "text_kor": clip_data.text_kor,
                    "note": clip_data.note,
                    "is_bookmarked": True,  # 배치의 각 클립은 북마크로 처리
                    "english_text": clip_data.text_eng,
                    "korean_text": clip_data.text_kor,
                    "duration": clip_data.end_time - clip_data.start_time
                }
                
                success = template_encoder.apply_template(
                    video_path=str(media_path),
                    output_path=str(output_path),
                    template_name=template_name,
                    segments=[segment]
                )
            else:
                # 기존 템플릿은 create_from_template 사용
                success = template_encoder.create_from_template(
                    template_name=template_name,
                    media_path=str(media_path),
                    subtitle_data=subtitle_data,
                    output_path=str(output_path),
                    start_time=clip_data.start_time,
                    end_time=clip_data.end_time,
                    padding_before=0.5,
                    padding_after=0.5,
                    save_individual_clips=request.individual_clips
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
        
        # 리뷰 클립은 이미 맨 처음에 생성했으므로 여기서는 건너뜀
        # (코드는 process_batch_clipping 함수 시작 부분에 있음)
        
        # 통합 비디오 생성
        combined_video_path = None
        if len(output_files) > 0:
            logger.info(f"[Job {job_id}] Creating combined video from {len(output_files)} clips")
            job_status[job_id]["progress"] = 95
            job_status[job_id]["message"] = "통합 비디오 생성 중..."
            
            # 통합 비디오 파일명
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_filename = f"{timestamp}_tp_{request.template_number}_combined.mp4"
            combined_video_path = job_dir / combined_filename
            
            # 리뷰 클립 위치에 따라 output_files에 추가
            review_clip_data = job_status[job_id].get("review_clip_data")
            if review_clip_data:
                logger.info(f"[Job {job_id}] Adding study clip, mode: {request.study}")
                if request.study == "preview":
                    # 맨 앞에 추가
                    logger.info(f"[Job {job_id}] Inserting study clip at the beginning")
                    output_files.insert(0, review_clip_data)
                else:  # "review"
                    # 맨 뒤에 추가
                    logger.info(f"[Job {job_id}] Appending study clip at the end")
                    output_files.append(review_clip_data)
            
            # filter_complex를 사용한 재인코딩 방식으로 비디오 합치기
            import subprocess
            
            # 입력 파일들 준비
            input_files = []
            filter_parts = []
            
            for idx, output_file in enumerate(output_files):
                file_path = Path(output_file["file"]).absolute()
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue
                input_files.extend(['-i', str(file_path)])
                # 각 입력에 대한 스트림 참조
                filter_parts.append(f"[{idx}:v][{idx}:a]")
            
            if len(input_files) == 0:
                logger.error("No valid input files for combining")
                raise Exception("No input files")
            
            # filter_complex 구성
            num_inputs = len(input_files) // 2
            filter_complex = f"{''.join(filter_parts)}concat=n={num_inputs}:v=1:a=1[outv][outa]"
            
            concat_cmd = [
                'ffmpeg',
                '-y'
            ] + input_files + [
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',  # 비디오 재인코딩
                '-preset', 'fast',
                '-crf', '20',
                '-c:a', 'aac',      # 오디오 재인코딩
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                '-movflags', '+faststart',
                str(combined_video_path)
            ]
            
            try:
                logger.info(f"Running FFmpeg concat command...")
                result = subprocess.run(concat_cmd, capture_output=True, text=True, check=True)
                logger.info(f"Combined video created successfully: {combined_video_path}")
                
                # 통합 비디오 정보 추가
                output_files.append({
                    "type": "combined",
                    "file": str(combined_video_path),
                    "total_clips": len(output_files),
                    "description": "통합 shadowing 비디오"
                })
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create combined video: {e.stderr}")
                logger.error(f"FFmpeg stdout: {e.stdout}")
                # 통합 비디오 생성 실패해도 개별 클립은 성공으로 처리
        else:
            logger.warning(f"[Job {job_id}] No output files to combine")
        
        # 메타데이터 저장
        metadata = {
            "job_id": job_id,
            "media_path": str(media_path),
            "template_number": request.template_number,
            "total_clips": len(request.clips),
            "output_files": output_files,
            "combined_video": str(combined_video_path) if combined_video_path else None,
            "study_mode": request.study,
            "review_clip": job_status[job_id].get("review_clip"),
            "created_at": datetime.now().isoformat()
        }
        
        with open(job_dir / "batch_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        
        # 완료 메시지 생성
        if request.study and review_clip_path:
            mode_text = "미리보기" if request.study == "preview" else "복습"
            message = f"배치 클리핑 완료! ({mode_text} 클립 + {len(request.clips)}개 클립 + 통합 비디오)"
        else:
            message = f"배치 클리핑 완료! ({len(request.clips)}개 클립 + 통합 비디오)"
        
        job_status[job_id]["message"] = message
        job_status[job_id]["output_files"] = output_files
        job_status[job_id]["combined_video"] = str(combined_video_path) if combined_video_path else None
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"배치 처리 오류: {str(e)}"


async def process_textbook_lesson(job_id: str, request: TextbookLessonRequest):
    """교재형 학습 비디오 처리"""
    try:
        # 작업 시작
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "교재형 학습 비디오 생성 중..."
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 날짜별 디렉토리 구조
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 출력 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{timestamp}_tp_{request.template_number}_textbook.mp4"
        output_path = job_dir / output_filename
        
        # 템플릿 이름 결정
        template_mapping = {
            91: "template_91",
            92: "template_92",
            93: "template_93"
        }
        
        template_name = template_mapping.get(request.template_number, "template_91")
        
        # 자막 세그먼트 데이터 준비
        segments = []
        for idx, segment in enumerate(request.subtitle_segments):
            segment_dict = segment.dict()
            # 템플릿 인코더가 기대하는 형식으로 변환
            segment_dict['english_text'] = segment_dict.get('text_eng', '')
            segment_dict['korean_text'] = segment_dict.get('text_kor', '')
            segment_dict['start_time'] = segment_dict.get('start_time', 0)
            segment_dict['duration'] = segment_dict.get('end_time', 0) - segment_dict.get('start_time', 0)
            # is_bookmarked는 그대로 유지
            segments.append(segment_dict)
            
        # 북마크 확인 로그
        bookmarked_count = sum(1 for seg in segments if seg.get('is_bookmarked', False))
        logger.info(f"[Job {job_id}] Processing {len(segments)} segments, {bookmarked_count} bookmarked")
        
        # 디버그: 세그먼트 내용 확인
        for i, seg in enumerate(segments[:3]):  # 처음 3개만
            logger.info(f"Segment {i}: is_bookmarked={seg.get('is_bookmarked')}, text_eng={seg.get('text_eng', '')[:30]}...")
        
        # 진행 상황 업데이트
        job_status[job_id]["progress"] = 20
        job_status[job_id]["message"] = "템플릿 비디오 인코더 초기화..."
        
        # 템플릿 비디오 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # apply_template 메서드 호출
        success = template_encoder.apply_template(
            video_path=str(media_path),
            output_path=str(output_path),
            template_name=template_name,
            segments=segments
        )
        
        if not success:
            raise Exception("Failed to create textbook lesson video")
        
        # 출력 파일 크기 확인
        if output_path.exists():
            file_size = output_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
        else:
            raise Exception("Output file not created")
        
        # 메타데이터 저장
        metadata = {
            "job_id": job_id,
            "media_path": str(media_path),
            "template_number": request.template_number,
            "lesson_title": request.lesson_title,
            "subtitle_segments": segments,
            "output_file": str(output_path),
            "file_size_mb": file_size_mb,
            "created_at": datetime.now().isoformat()
        }
        
        with open(job_dir / "textbook_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 작업 완료
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["progress"] = 100
        # 북마크된 세그먼트 개수 계산
        bookmarked_count = sum(1 for seg in request.subtitle_segments if seg.is_bookmarked)
        job_status[job_id]["message"] = f"교재형 학습 비디오 생성 완료! ({bookmarked_count}개 북마크)"
        job_status[job_id]["output_file"] = str(output_path)
        job_status[job_id]["file_size_mb"] = file_size_mb
        
        # DB에 저장
        job_data_for_db = {
            "status": "completed",
            "progress": 100,
            "media_path": str(media_path),
            "template_number": request.template_number,
            "start_time": request.subtitle_segments[0].start_time if request.subtitle_segments else 0,
            "end_time": request.subtitle_segments[-1].end_time if request.subtitle_segments else 0,
            "output_file": str(output_path),
            "output_size": file_size,
            "text_eng": request.lesson_title,
            "text_kor": f"{bookmarked_count}개 북마크",
            "note": json.dumps({"lesson_title": request.lesson_title}),
            "keywords": []
        }
        save_job_to_db(job_id, job_data_for_db)
        
    except Exception as e:
        logger.error(f"Error creating textbook lesson: {e}", exc_info=True)
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"교재형 학습 비디오 생성 오류: {str(e)}"
        
        # DB에 실패 상태 저장
        job_data_for_db = {
            "status": "failed",
            "progress": 0,
            "media_path": request.media_path,
            "template_number": request.template_number,
            "start_time": 0,
            "end_time": 0,
            "error_message": str(e)
        }
        save_job_to_db(job_id, job_data_for_db)


async def _process_template_91_single_clip(job_id: str, request: ClippingRequest):
    """Template 91 단일 클립 처리 (apply_template 방식 사용)"""
    try:
        logger.info(f"=== Template 91 processing started for job_id: {job_id} ===")
        logger.info(f"Request details: media_path={request.media_path}, start_time={request.start_time}, end_time={request.end_time}")
        
        # 작업 시작
        update_job_status_both(job_id, "processing", 10, message="Template 91 클리핑 준비 중...")
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        
        # 작업 디렉토리 생성
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        job_dir = daily_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # 단일 세그먼트 생성 (북마크로 처리)
        segment = {
            "start_time": request.start_time,
            "end_time": request.end_time,
            "text_eng": request.text_eng,
            "text_kor": request.text_kor,
            "note": request.note or "",
            "is_bookmarked": True  # 단일 클립은 북마크로 처리
        }
        
        # 날짜시간_tp_91.mp4 형식의 파일명 생성
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_tp_91.mp4"
        output_path = job_dir / filename
        
        update_job_status_both(job_id, "processing", 30, message="Template 91 비디오 생성 중...")
        
        logger.info(f"Creating template 91 video at: {output_path}")
        logger.info(f"Segment data: {segment}")
        
        # TemplateVideoEncoder의 apply_template 방식 사용
        from template_video_encoder import TemplateVideoEncoder
        template_encoder = TemplateVideoEncoder()
        
        # apply_template 방식으로 처리 (올바른 파라미터 순서)
        logger.info("Calling template_encoder.apply_template...")
        success = template_encoder.apply_template(
            video_path=str(media_path),
            output_path=str(output_path),
            template_name="template_91",
            segments=[segment]  # 단일 세그먼트
        )
        logger.info(f"Template encoder returned: {success}")
        
        if success and output_path.exists():
            update_job_status_both(job_id, "processing", 90, message="Template 91 클리핑 완료, 파일 정리 중...")
            
            # 파일 크기 계산
            file_size = output_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # 메타데이터 저장
            metadata = {
                "job_id": job_id,
                "media_path": str(media_path),
                "template_number": 91,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "text_eng": request.text_eng,
                "text_kor": request.text_kor,
                "note": request.note,
                "output_file": str(output_path),
                "file_size_mb": file_size_mb,
                "created_at": datetime.now().isoformat()
            }
            
            with open(job_dir / "template_91_metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 작업 완료
            job_status[job_id]["status"] = "completed"
            job_status[job_id]["progress"] = 100
            job_status[job_id]["message"] = "Template 91 클리핑 완료!"
            job_status[job_id]["output_file"] = str(output_path)
            job_status[job_id]["file_size_mb"] = file_size_mb
            
            # DB에 저장
            job_data_for_db = {
                "status": "completed",
                "progress": 100,
                "media_path": str(media_path),
                "template_number": 91,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "output_file": str(output_path),
                "output_size": file_size,
                "text_eng": request.text_eng,
                "text_kor": request.text_kor,
                "note": request.note or "",
                "keywords": []
            }
            save_job_to_db(job_id, job_data_for_db)
            
            logger.info(f"=== Template 91 클리핑 완료 ===\nOutput: {output_path}\nSize: {file_size_mb}MB")
            logger.info(f"Job {job_id} completed successfully")
            
        else:
            raise Exception("Template 91 비디오 생성 실패")
            
    except Exception as e:
        logger.error(f"Template 91 클리핑 오류: {e}", exc_info=True)
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"Template 91 클리핑 오류: {str(e)}"
        
        # DB에 실패 상태 저장
        job_data_for_db = {
            "status": "failed",
            "progress": 0,
            "media_path": request.media_path,
            "template_number": 91,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "error_message": str(e)
        }
        save_job_to_db(job_id, job_data_for_db)


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
         summary="배치 클립 다운로드")
async def download_batch_clip(job_id: str, clip_num: str):
    """배치 작업의 클립을 다운로드합니다. clip_num이 'combined'인 경우 통합 비디오를 다운로드합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    # 날짜별 디렉토리에서 job_id 찾기
    job_path = None
    for daily_dir in OUTPUT_DIR.iterdir():
        if daily_dir.is_dir() and (daily_dir / job_id).exists():
            job_path = daily_dir / job_id
            break
    
    if not job_path:
        raise HTTPException(status_code=404, detail="Job directory not found")
    
    # 통합 비디오 다운로드
    if clip_num == "combined":
        # 통합 비디오 파일 찾기
        combined_files = list(job_path.glob("*_combined.mp4"))
        if not combined_files:
            raise HTTPException(status_code=404, detail="Combined video not found")
        
        combined_path = combined_files[0]
        return FileResponse(
            combined_path,
            media_type="video/mp4",
            filename=f"batch_{job_id}_combined.mp4"
        )
    
    # 개별 클립 다운로드
    try:
        clip_num_int = int(clip_num)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid clip number")
    
    # 클립 파일 찾기 (여러 가능한 경로 시도)
    possible_paths = [
        job_path / f"clip_{clip_num_int:03d}" / f"*_c{clip_num_int:03d}.mp4",  # 새 형식
        job_path / f"clip_{clip_num_int:03d}" / f"clip_{clip_num_int:03d}.mp4",  # 이전 형식
        job_path / f"clip_{clip_num_int:03d}" / "*.mp4"  # 모든 mp4 파일
    ]
    
    clip_path = None
    for pattern in possible_paths:
        matches = list(job_path.glob(str(pattern).split('/')[-2] + '/' + str(pattern).split('/')[-1]))
        if matches:
            clip_path = matches[0]
            break
    
    if not clip_path or not clip_path.exists():
        raise HTTPException(status_code=404, detail=f"Clip {clip_num} not found")
    
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"batch_{job_id}_clip_{clip_num_int:03d}.mp4"
    )


@app.delete("/api/job/{job_id}",
            tags=["Management"],
            summary="작업 삭제")
async def delete_job_api(job_id: str, force: bool = False):
    """작업과 관련 파일을 삭제합니다. force=true인 경우 파일이 없어도 DB 레코드를 삭제합니다."""
    
    # DB에서 작업 찾기
    db_job = get_job_by_id(job_id)
    if not db_job:
        # 메모리에서도 확인
        if job_id not in job_status:
            raise HTTPException(status_code=404, detail="Job not found in database or memory")
    
    # 파일 삭제 시도
    job_dir = None
    file_deleted = False
    
    # 날짜별 디렉토리에서 job_id 찾기
    for daily_dir in OUTPUT_DIR.iterdir():
        if daily_dir.is_dir() and (daily_dir / job_id).exists():
            job_dir = daily_dir / job_id
            break
    
    # 파일이 없는 경우 처리
    if not job_dir or not job_dir.exists():
        if not force:
            # force가 아니면 에러
            logger.warning(f"Job directory not found for {job_id}, but force={force}")
            if not force:
                raise HTTPException(status_code=404, detail="Job directory not found. Use force=true to delete DB record anyway.")
    else:
        # 파일이 있으면 삭제
        try:
            import shutil
            shutil.rmtree(job_dir)
            file_deleted = True
            logger.info(f"Deleted job directory: {job_dir}")
        except Exception as e:
            logger.error(f"Failed to delete directory {job_dir}: {e}")
            if not force:
                raise HTTPException(status_code=500, detail=f"Failed to delete files: {str(e)}")
    
    # 메모리에서 삭제
    if job_id in job_status:
        del job_status[job_id]
    
    # DB에서 삭제
    if db_job:
        delete_job(job_id)  # database.py의 delete_job 함수 호출
    
    return {
        "message": "Job deleted successfully",
        "file_deleted": file_deleted,
        "db_deleted": True
    }


# 정리 작업 (만료된 작업 제거)
async def cleanup_expired_jobs():
    """만료된 작업 정리"""
    while True:
        try:
            current_time = datetime.now()
            expired_jobs = []
            
            for job_id, status in job_status.items():
                # 생성 시간 확인 (메타데이터에서) - 날짜별 디렉토리에서 찾기
                metadata_path = None
                for daily_dir in OUTPUT_DIR.iterdir():
                    if daily_dir.is_dir() and (daily_dir / job_id / "metadata.json").exists():
                        metadata_path = daily_dir / job_id / "metadata.json"
                        break
                if metadata_path and metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        created_at = datetime.fromisoformat(metadata.get('created_at', current_time.isoformat()))
                        
                        # 24시간 경과 확인
                        if (current_time - created_at).total_seconds() > JOB_EXPIRE_TIME:
                            expired_jobs.append(job_id)
            
            # 만료된 작업 제거
            for job_id in expired_jobs:
                try:
                    # 파일 삭제 - 날짜별 디렉토리에서 job_id 찾기
                    job_dir = None
                    for daily_dir in OUTPUT_DIR.iterdir():
                        if daily_dir.is_dir() and (daily_dir / job_id).exists():
                            job_dir = daily_dir / job_id
                            break
                    
                    if not job_dir:
                        continue  # job_dir를 찾을 수 없으면 다음으로
                    
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


# Admin API endpoints
@app.get("/api/admin/statistics",
         tags=["Admin"],
         summary="통계 정보 조회")
async def get_admin_statistics():
    """클리핑 작업 통계 정보를 조회합니다."""
    return get_statistics()


@app.get("/api/admin/jobs/recent",
         tags=["Admin"],
         summary="최근 작업 목록 조회")
async def get_recent_jobs_api(limit: int = 50):
    """최근 생성된 작업 목록을 조회합니다."""
    jobs = get_recent_jobs(limit)
    return [
        {
            "id": job.id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "media_path": job.media_path,
            "media_filename": Path(job.media_path).name if job.media_path else None,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "template_number": job.template_number,
            "status": job.status,
            "progress": job.progress,
            "output_file": job.output_file,
            "output_size": job.output_size,
            "duration": job.duration,
            "text_eng": job.text_eng,
            "text_kor": job.text_kor,
            "keywords": json.loads(job.keywords) if job.keywords and isinstance(job.keywords, str) else job.keywords or [],
            "error_message": job.error_message
        }
        for job in jobs
    ]


@app.get("/api/admin/jobs/search",
         tags=["Admin"],
         summary="작업 검색")
async def search_jobs_api(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """조건에 맞는 작업을 검색합니다."""
    jobs = search_jobs(keyword, status, start_date, end_date)
    return [
        {
            "id": job.id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "media_path": job.media_path,
            "media_filename": Path(job.media_path).name if job.media_path else None,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "template_number": job.template_number,
            "status": job.status,
            "progress": job.progress,
            "output_file": job.output_file,
            "output_size": job.output_size,
            "duration": job.duration,
            "text_eng": job.text_eng,
            "text_kor": job.text_kor,
            "keywords": json.loads(job.keywords) if job.keywords and isinstance(job.keywords, str) else job.keywords or [],
            "error_message": job.error_message
        }
        for job in jobs
    ]


@app.post("/api/admin/cleanup",
         tags=["Admin"],
         summary="고아 레코드 정리")
async def cleanup_orphaned_records():
    """파일이 없는 DB 레코드를 정리합니다."""
    try:
        jobs = get_recent_jobs(limit=1000)  # 최근 1000개 확인
        deleted_count = 0
        checked_count = 0
        
        for job in jobs:
            checked_count += 1
            job_id = job.id
            
            # 파일 존재 확인
            file_exists = False
            
            # 날짜별 디렉토리에서 확인
            for daily_dir in OUTPUT_DIR.iterdir():
                if daily_dir.is_dir() and (daily_dir / job_id).exists():
                    file_exists = True
                    break
            
            # output_file 경로로도 확인
            if not file_exists and job.output_file:
                file_exists = Path(job.output_file).exists()
            
            # 파일이 없으면 DB에서 삭제
            if not file_exists:
                logger.info(f"Deleting orphaned record: {job_id}")
                delete_job(job_id)
                deleted_count += 1
                
                # 메모리에서도 삭제
                if job_id in job_status:
                    del job_status[job_id]
        
        logger.info(f"Cleanup completed: checked={checked_count}, deleted={deleted_count}")
        
        return {
            "checked_count": checked_count,
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} orphaned records out of {checked_count} checked"
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/jobs/{job_id}",
         tags=["Admin"],
         summary="작업 상세 조회")
async def get_job_detail_api(job_id: str):
    """특정 작업의 상세 정보를 조회합니다."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "media_path": job.media_path,
        "media_filename": Path(job.media_path).name if job.media_path else None,
        "start_time": job.start_time,
        "end_time": job.end_time,
        "duration": job.duration,
        "template_number": job.template_number,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "output_file": job.output_file,
        "output_size": job.output_size,
        "individual_clips": json.loads(job.individual_clips) if job.individual_clips and isinstance(job.individual_clips, str) else job.individual_clips,
        "text_eng": job.text_eng,
        "text_kor": job.text_kor,
        "note": job.note,
        "keywords": json.loads(job.keywords) if job.keywords and isinstance(job.keywords, str) else job.keywords or [],
        "error_message": job.error_message,
        "client_ip": job.client_ip
    }


@app.delete("/api/admin/jobs",
            tags=["Admin"],
            summary="작업 일괄 삭제")
async def delete_jobs_api(
    job_ids: List[str],
    delete_files: bool = True
):
    """여러 작업을 일괄 삭제합니다."""
    result = delete_jobs_bulk(job_ids, delete_files)
    return {
        "deleted_count": result['deleted_count'],
        "failed_deletes": result.get('failed_deletes', [])
    }


@app.post("/api/admin/cleanup",
          tags=["Admin"],
          summary="오래된 작업 정리")
async def cleanup_old_jobs_api(
    days_old: int = 30,
    delete_files: bool = True
):
    """지정된 일수보다 오래된 작업을 정리합니다."""
    result = cleanup_old_jobs(days_old, delete_files)
    return {
        "deleted_count": result['deleted_count']
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """헬스체크 엔드포인트"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "redis": USE_REDIS,
        "memory_jobs": len(job_status) if not USE_REDIS else 0,
        "active_processes": len(active_processes),
        "disk_usage": {}
    }
    
    try:
        # 디스크 사용량 체크
        import shutil
        total, used, free = shutil.disk_usage(str(OUTPUT_DIR))
        health_status["disk_usage"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "usage_percent": round(used / total * 100, 2)
        }
        
        # 디스크 공간 부족 경고
        if health_status["disk_usage"]["usage_percent"] > 90:
            health_status["status"] = "warning"
            health_status["message"] = "Disk usage is over 90%"
    except Exception as e:
        health_status["disk_error"] = str(e)
    
    return health_status

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 이벤트"""
    # 데이터베이스 초기화
    init_db()
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
    
    # SSL 설정
    ssl_keyfile = os.getenv("SSL_KEYFILE", "ssl/key.pem")
    ssl_certfile = os.getenv("SSL_CERTFILE", "ssl/cert.pem")
    use_ssl = os.getenv("USE_SSL", "true").lower() == "true"
    
    # SSL 파일 존재 여부 확인
    if use_ssl and (not os.path.exists(ssl_keyfile) or not os.path.exists(ssl_certfile)):
        logger.warning(f"SSL files not found: {ssl_keyfile}, {ssl_certfile}. Running without SSL.")
        use_ssl = False
    
    uvicorn_config = {
        "app": app,
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", 8080)),
        "workers": int(os.getenv("WORKERS", 1)),
        "log_config": log_config,
        "access_log": True
    }
    
    # SSL 설정 추가
    if use_ssl:
        uvicorn_config.update({
            "ssl_keyfile": ssl_keyfile,
            "ssl_certfile": ssl_certfile
        })
        logger.info(f"Starting server with SSL on port {uvicorn_config['port']}")
    else:
        logger.info(f"Starting server without SSL on port {uvicorn_config['port']}")
    
    uvicorn.run(**uvicorn_config)

@app.post("/api/job/{job_id}/cancel",
         tags=["Job Management"],
         summary="작업 취소",
         response_model=Dict[str, str])
async def cancel_job_api(job_id: str):
    """실행 중인 작업을 취소합니다."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    if job["status"] not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in {job['status']} state")
    
    # 프로세스 정리
    cleanup_job_processes(job_id)
    
    # 상태 업데이트
    update_job_status_both(job_id, "cancelled", error_message="User cancelled the job")
    
    return {"message": "Job cancelled successfully"}

