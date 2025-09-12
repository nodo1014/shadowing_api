"""
Database utility functions for API routes
Handles DB operations for jobs, videos, and logging
"""

import os
import sys
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_v2.models_v2 import (
    DatabaseManager, Job, Template, MediaSource, Subtitle, 
    OutputVideo, ProcessingLog, APIRequest
)
from api.config import logger

def create_job_in_db(
    session: Session,
    job_id: str,
    job_type: str,
    api_endpoint: str,
    request_data: Dict,
    client_info: Dict,
    extra_data: Optional[Dict] = None
) -> Job:
    """Create a new job in database"""
    
    job = Job(
        id=job_id,
        job_type=job_type,
        status="pending",
        api_endpoint=api_endpoint,
        request_method="POST",
        request_headers=json.dumps(client_info.get("headers", {})),
        request_body=json.dumps(request_data),
        client_ip=client_info.get("ip"),
        user_agent=client_info.get("user_agent"),
        referer=client_info.get("referer"),
        origin=client_info.get("origin"),
        template_id=request_data.get("template_number"),
        start_time=request_data.get("start_time"),
        end_time=request_data.get("end_time"),
        duration=request_data.get("duration"),
        user_id=request_data.get("user_id"),
        extra_data=extra_data or {}
    )
    
    session.add(job)
    session.commit()
    
    return job

def create_media_source(
    session: Session,
    job_id: str,
    file_path: str,
    youtube_url: Optional[str] = None,
    youtube_info: Optional[Dict] = None
) -> MediaSource:
    """Create media source record"""
    
    media = MediaSource(
        job_id=job_id,
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        youtube_url=youtube_url,
        youtube_title=youtube_info.get("title") if youtube_info else None,
        youtube_channel=youtube_info.get("uploader") if youtube_info else None
    )
    
    session.add(media)
    session.commit()
    
    return media

def create_subtitle_record(
    session: Session,
    job_id: str,
    text_eng: Optional[str] = None,
    text_kor: Optional[str] = None,
    note: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
) -> Subtitle:
    """Create subtitle record"""
    
    subtitle = Subtitle(
        job_id=job_id,
        text_eng=text_eng,
        text_kor=text_kor,
        note=note,
        keywords=json.dumps(keywords) if keywords else None,
        start_time=start_time,
        end_time=end_time
    )
    
    session.add(subtitle)
    session.commit()
    
    return subtitle

def create_output_video(
    session: Session,
    job_id: str,
    video_type: str,
    file_path: str,
    effect_type: Optional[str] = None,
    subtitle_mode: Optional[str] = None,
    clip_index: Optional[int] = None,
    processing_time: Optional[float] = None
) -> OutputVideo:
    """Create output video record"""
    
    # Get file info
    file_size = 0
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
    
    video = OutputVideo(
        job_id=job_id,
        video_type=video_type,
        clip_index=clip_index,
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size=file_size,
        effect_type=effect_type,
        subtitle_mode=subtitle_mode,
        processing_time=processing_time
    )
    
    # Try to get video metadata with ffprobe
    try:
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate,codec_name,bit_rate',
            '-of', 'json',
            file_path
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get('streams'):
                stream = data['streams'][0]
                video.width = stream.get('width')
                video.height = stream.get('height')
                video.duration = float(stream.get('duration', 0))
                video.codec = stream.get('codec_name')
                video.bitrate = int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None
                
                # Parse FPS
                if stream.get('r_frame_rate'):
                    fps_parts = stream['r_frame_rate'].split('/')
                    if len(fps_parts) == 2 and fps_parts[1] != '0':
                        video.fps = float(fps_parts[0]) / float(fps_parts[1])
    except Exception as e:
        logger.warning(f"Failed to get video metadata: {e}")
    
    session.add(video)
    session.commit()
    
    return video

def update_job_status_db(
    session: Session,
    job_id: str,
    status: str,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[Job]:
    """Update job status in database"""
    
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        logger.warning(f"Job {job_id} not found in database")
        return None
    
    job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if error_message is not None:
        job.error_message = error_message
    
    # Update timestamps
    if status == "processing" and not job.started_at:
        job.started_at = datetime.utcnow()
    elif status in ["completed", "failed"]:
        job.completed_at = datetime.utcnow()
        if job.started_at:
            job.processing_duration = (job.completed_at - job.started_at).total_seconds()
    
    session.commit()
    return job

def add_processing_log(
    session: Session,
    job_id: str,
    level: str,
    stage: str,
    message: str,
    details: Optional[Dict] = None
) -> ProcessingLog:
    """Add processing log entry"""
    
    log = ProcessingLog(
        job_id=job_id,
        level=level,
        stage=stage,
        message=message,
        details=json.dumps(details) if details else None
    )
    
    session.add(log)
    session.commit()
    
    return log

def log_api_request(
    session: Session,
    endpoint: str,
    method: str,
    client_info: Dict,
    request_data: Optional[Dict] = None,
    response_status: Optional[int] = None,
    response_time_ms: Optional[int] = None,
    response_body: Optional[Dict] = None,
    error: Optional[str] = None,
    job_id: Optional[str] = None
) -> APIRequest:
    """Log API request"""
    
    api_request = APIRequest(
        job_id=job_id,
        endpoint=endpoint,
        method=method,
        client_ip=client_info.get("ip"),
        user_agent=client_info.get("user_agent"),
        referer=client_info.get("referer"),
        origin=client_info.get("origin"),
        request_headers=json.dumps(client_info.get("headers", {})),
        request_body=json.dumps(request_data) if request_data else None,
        response_status=response_status,
        response_time_ms=response_time_ms,
        response_body=json.dumps(response_body) if response_body else None,
        error_message=error
    )
    
    session.add(api_request)
    session.commit()
    
    return api_request

def get_client_info(request) -> Dict:
    """Extract client information from request"""
    
    headers = dict(request.headers)
    
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": headers.get("user-agent"),
        "referer": headers.get("referer"),
        "origin": headers.get("origin"),
        "headers": headers
    }

def guess_effect_type(file_path: str) -> str:
    """Guess effect type from filename"""
    if 'blur' in file_path:
        return 'blur'
    elif 'crop' in file_path:
        return 'crop'
    elif 'fit' in file_path:
        return 'fit'
    return 'none'

def guess_subtitle_mode(file_path: str) -> str:
    """Guess subtitle mode from filename"""
    if 'nosub' in file_path:
        return 'nosub'
    elif 'korean' in file_path:
        return 'korean'
    elif 'both' in file_path:
        return 'both'
    return 'both'  # Default

def ensure_templates_populated(session: Session):
    """Ensure templates table is populated"""
    
    # Check if templates exist
    template_count = session.query(Template).count()
    if template_count > 0:
        return
    
    # Load templates from JSON
    templates_file = "templates/shadowing_patterns.json"
    if not os.path.exists(templates_file):
        logger.warning(f"Templates file not found: {templates_file}")
        return
    
    with open(templates_file, 'r') as f:
        templates_data = json.load(f)
    
    for template in templates_data.get('templates', []):
        db_template = Template(
            id=template['number'],
            name=template.get('name', f"Template {template['number']}"),
            category='shorts' if template.get('is_shorts') else 'general',
            resolution_width=1080 if template.get('is_shorts') else 1920,
            resolution_height=1920 if template.get('is_shorts') else 1080,
            config=template
        )
        session.add(db_template)
    
    session.commit()
    logger.info(f"Populated {len(templates_data.get('templates', []))} templates")