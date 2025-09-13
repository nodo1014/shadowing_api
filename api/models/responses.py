"""
API Response Models
"""
from typing import Optional, List, Any
from pydantic import BaseModel


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
    output_files: Optional[List[Any]] = None  # 배치 작업의 출력 파일 목록
    individual_clips_dir: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None
    
    class Config:
        extra = "allow"  # 추가 필드 허용