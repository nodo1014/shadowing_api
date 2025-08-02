"""
Standardized API response models
표준화된 API 응답 모델
"""
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime

class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = False
    error_code: str = Field(..., description="Error code for client handling")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

class JobResponse(BaseResponse):
    """Job creation/status response"""
    success: bool = True
    job_id: str = Field(..., description="Job UUID")
    status: str = Field(..., description="Job status")
    progress: int = Field(0, description="Progress percentage")
    output_file: Optional[str] = Field(None, description="Output file path when completed")

class BatchJobResponse(BaseResponse):
    """Batch job response"""
    success: bool = True
    batch_id: str = Field(..., description="Batch job UUID")
    total_clips: int = Field(..., description="Total number of clips")
    status: str = Field(..., description="Batch status")
    clips: List[Dict[str, Any]] = Field(default_factory=list, description="Individual clip statuses")

class HealthCheckResponse(BaseResponse):
    """Health check response"""
    success: bool = True
    service: str = "Video Clipping API"
    version: str = "1.0.0"
    redis_status: str = Field(..., description="Redis connection status")
    database_status: str = Field(..., description="Database connection status")
    active_jobs: int = Field(..., description="Number of active jobs")

class StatisticsResponse(BaseResponse):
    """Statistics response"""
    success: bool = True
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    success_rate: float
    total_duration_seconds: float
    total_output_size_mb: float

def create_success_response(message: str, **kwargs) -> Dict[str, Any]:
    """Create a standardized success response"""
    return {
        "success": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }

def create_error_response(message: str, error_code: str, **kwargs) -> Dict[str, Any]:
    """Create a standardized error response"""
    return {
        "success": False,
        "message": message,
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }