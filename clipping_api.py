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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', '/mnt/ssd1t/output'))
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
    template_number: int = Field(1, ge=1, le=3, description="템플릿 번호 (1, 2, 또는 3)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")


class BatchClippingRequest(BaseModel):
    """배치 클리핑 요청 모델"""
    media_path: str = Field(..., description="미디어 파일 경로")
    clips: List[ClipData] = Field(..., description="클립 데이터 리스트")
    template_number: int = Field(1, ge=1, le=3, description="템플릿 번호 (1, 2, 또는 3)")
    individual_clips: bool = Field(True, description="개별 클립 저장 여부")
    
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
                "template_number": 1,
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
        
        # 자막 데이터 준비
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'english': request.text_eng,
            'korean': request.text_kor,
            'note': request.note,
            'eng': request.text_eng,  # 호환성
            'kor': request.text_kor,   # 호환성
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
        
        # 템플릿 이름 결정
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
            
            # 자막 데이터
            subtitle_data = {
                'start_time': 0,
                'end_time': clip_data.end_time - clip_data.start_time,
                'english': clip_data.text_eng,
                'korean': clip_data.text_kor,
                'note': clip_data.note,
                'eng': clip_data.text_eng,
                'kor': clip_data.text_kor,
                'keywords': clip_data.keywords,  # Type 2를 위한 키워드
                'template_number': request.template_number,  # 클리핑 타입 전달
                'text_eng_blank': text_eng_blank  # Type 2를 위한 blank 텍스트
            }
            
            # 비디오 클리핑 - 템플릿 기반 (자막 파일 자동 생성)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_tp_{request.template_number}_c{clip_num:03d}.mp4"
            output_path = clip_dir / filename
            
            # 템플릿 기반 인코더 사용
            template_encoder = TemplateVideoEncoder()
            template_name = f"template_{request.template_number}"
            
            # 템플릿을 사용하여 비디오 생성
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
        
        # 메타데이터 저장
        metadata = {
            "job_id": job_id,
            "media_path": str(media_path),
            "template_number": request.template_number,
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
    
    # 날짜별 디렉토리에서 job_id 찾기
    job_path = None
    for daily_dir in OUTPUT_DIR.iterdir():
        if daily_dir.is_dir() and (daily_dir / job_id).exists():
            job_path = daily_dir / job_id
            break
    
    if not job_path:
        raise HTTPException(status_code=404, detail="Job directory not found")
    
    clip_path = job_path / f"clip_{clip_num:03d}" / f"clip_{clip_num:03d}.mp4"
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
    # 날짜별 디렉토리에서 job_id 찾기
    job_dir = None
    for daily_dir in OUTPUT_DIR.iterdir():
        if daily_dir.is_dir() and (daily_dir / job_id).exists():
            job_dir = daily_dir / job_id
            break
    
    if not job_dir:
        raise HTTPException(status_code=404, detail="Job directory not found")
    
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

