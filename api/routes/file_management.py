#!/usr/bin/env python3
"""
File Management API Routes
Provides endpoints for searching, filtering, and deleting video files
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import json

# Import database models and utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database_v2.models_v2 import (
    DatabaseManager, Job, OutputVideo, FileDeletionLog,
    get_videos_by_filter
)
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

# Import existing utilities
from api.config import logger, OUTPUT_DIR
from api.utils import get_job_status

router = APIRouter(prefix="/api/files", tags=["file_management"])

# Database session dependency
def get_db():
    db_manager = DatabaseManager()
    try:
        yield db_manager.get_session()
    finally:
        db_manager.close()

@router.get("/search")
async def search_files(
    # Filters
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    template_id: Optional[int] = Query(None, description="Template ID"),
    status: Optional[str] = Query(None, description="Job status"),
    video_type: Optional[str] = Query(None, description="Video type (final/individual/preview/review)"),
    effect_type: Optional[str] = Query(None, description="Effect type (blur/crop/fit/none)"),
    subtitle_mode: Optional[str] = Query(None, description="Subtitle mode (nosub/korean/both)"),
    text_search: Optional[str] = Query(None, description="Search in subtitle text"),
    min_size_mb: Optional[float] = Query(None, description="Minimum file size in MB"),
    max_size_mb: Optional[float] = Query(None, description="Maximum file size in MB"),
    
    # Pagination
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    
    # Sorting
    sort_by: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    
    # Database session
    db: Session = Depends(get_db)
):
    """Search and filter video files with various criteria"""
    
    try:
        # Build query
        query = db.query(OutputVideo).join(Job)
        
        # Apply filters
        if date_from:
            query = query.filter(OutputVideo.created_at >= date_from)
        if date_to:
            query = query.filter(OutputVideo.created_at <= date_to)
        if template_id:
            query = query.filter(Job.template_id == template_id)
        if status:
            query = query.filter(Job.status == status)
        if video_type:
            query = query.filter(OutputVideo.video_type == video_type)
        if effect_type:
            query = query.filter(OutputVideo.effect_type == effect_type)
        if subtitle_mode:
            query = query.filter(OutputVideo.subtitle_mode == subtitle_mode)
        
        # File size filters
        if min_size_mb:
            query = query.filter(OutputVideo.file_size >= min_size_mb * 1024 * 1024)
        if max_size_mb:
            query = query.filter(OutputVideo.file_size <= max_size_mb * 1024 * 1024)
        
        # Text search in subtitles
        if text_search:
            from database_v2.models_v2 import Subtitle
            search_term = f"%{text_search}%"
            query = query.join(Subtitle, Job.id == Subtitle.job_id).filter(
                or_(
                    Subtitle.text_eng.like(search_term),
                    Subtitle.text_kor.like(search_term),
                    Subtitle.note.like(search_term)
                )
            )
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if hasattr(OutputVideo, sort_by):
            sort_column = getattr(OutputVideo, sort_by)
            if order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * per_page
        videos = query.offset(offset).limit(per_page).all()
        
        # Format response
        results = []
        for video in videos:
            # Check if file exists
            file_exists = os.path.exists(video.file_path)
            
            results.append({
                "id": video.id,
                "job_id": video.job_id,
                "file_path": video.file_path,
                "file_name": video.file_name,
                "file_size": video.file_size,
                "file_size_mb": round(video.file_size / 1024 / 1024, 2) if video.file_size else 0,
                "file_exists": file_exists,
                "video_type": video.video_type,
                "effect_type": video.effect_type,
                "subtitle_mode": video.subtitle_mode,
                "duration": video.duration,
                "resolution": f"{video.width}x{video.height}" if video.width and video.height else None,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "view_count": video.view_count,
                "job": {
                    "status": video.job.status,
                    "template_id": video.job.template_id,
                    "client_ip": video.job.client_ip,
                    "created_at": video.job.created_at.isoformat() if video.job.created_at else None
                }
            })
        
        return {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete/batch")
async def delete_files_batch(
    request: Request,
    video_ids: List[int],
    backup: bool = False,
    reason: str = "manual",
    db: Session = Depends(get_db)
):
    """Delete multiple video files"""
    
    try:
        deleted_files = []
        failed_files = []
        
        # Get client info
        client_ip = request.client.host
        
        for video_id in video_ids:
            try:
                # Get video info
                video = db.query(OutputVideo).filter(OutputVideo.id == video_id).first()
                if not video:
                    failed_files.append({"id": video_id, "error": "Video not found"})
                    continue
                
                # Backup if requested
                backup_location = None
                if backup and os.path.exists(video.file_path):
                    backup_dir = Path("file_backups") / datetime.now().strftime("%Y%m%d")
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_location = str(backup_dir / video.file_name)
                    shutil.copy2(video.file_path, backup_location)
                
                # Delete physical file
                if os.path.exists(video.file_path):
                    os.remove(video.file_path)
                
                # Log deletion
                deletion_log = FileDeletionLog(
                    job_id=video.job_id,
                    output_video_id=video.id,
                    file_path=video.file_path,
                    file_size=video.file_size,
                    deleted_by=client_ip,
                    deletion_reason=reason,
                    is_backed_up=backup,
                    backup_location=backup_location,
                    metadata=json.dumps({
                        "video_type": video.video_type,
                        "effect_type": video.effect_type,
                        "subtitle_mode": video.subtitle_mode
                    })
                )
                db.add(deletion_log)
                
                # Remove from database
                db.delete(video)
                
                deleted_files.append({
                    "id": video_id,
                    "file_path": video.file_path,
                    "backup_location": backup_location
                })
                
            except Exception as e:
                failed_files.append({"id": video_id, "error": str(e)})
        
        # Commit all changes
        db.commit()
        
        return {
            "deleted": len(deleted_files),
            "failed": len(failed_files),
            "deleted_files": deleted_files,
            "failed_files": failed_files
        }
        
    except Exception as e:
        logger.error(f"Batch delete error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jobs/{job_id}/cascade")
async def delete_job_cascade(
    job_id: str,
    request: Request,
    backup: bool = False,
    db: Session = Depends(get_db)
):
    """Delete a job and all its associated files"""
    
    try:
        # Get job with all videos
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get all output videos
        videos = db.query(OutputVideo).filter(OutputVideo.job_id == job_id).all()
        
        deleted_files = []
        client_ip = request.client.host
        
        # Delete each video file
        for video in videos:
            try:
                # Backup if requested
                backup_location = None
                if backup and os.path.exists(video.file_path):
                    backup_dir = Path("file_backups") / datetime.now().strftime("%Y%m%d")
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_location = str(backup_dir / video.file_name)
                    shutil.copy2(video.file_path, backup_location)
                
                # Delete physical file
                if os.path.exists(video.file_path):
                    os.remove(video.file_path)
                
                # Log deletion
                deletion_log = FileDeletionLog(
                    job_id=job_id,
                    output_video_id=video.id,
                    file_path=video.file_path,
                    file_size=video.file_size,
                    deleted_by=client_ip,
                    deletion_reason="cascade",
                    is_backed_up=backup,
                    backup_location=backup_location
                )
                db.add(deletion_log)
                
                deleted_files.append({
                    "file_path": video.file_path,
                    "backup_location": backup_location
                })
                
            except Exception as e:
                logger.warning(f"Failed to delete file {video.file_path}: {e}")
        
        # Delete the job (cascade will delete related records)
        db.delete(job)
        db.commit()
        
        return {
            "job_id": job_id,
            "deleted_files": len(deleted_files),
            "files": deleted_files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cascade delete error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage/stats")
async def get_storage_stats(db: Session = Depends(get_db)):
    """Get storage usage statistics"""
    
    try:
        # Get total file count and size
        stats = db.query(
            func.count(OutputVideo.id).label('total_files'),
            func.sum(OutputVideo.file_size).label('total_size'),
            func.avg(OutputVideo.file_size).label('avg_size')
        ).first()
        
        # Get stats by video type
        type_stats = db.query(
            OutputVideo.video_type,
            func.count(OutputVideo.id).label('count'),
            func.sum(OutputVideo.file_size).label('size')
        ).group_by(OutputVideo.video_type).all()
        
        # Get stats by template
        template_stats = db.query(
            Job.template_id,
            func.count(OutputVideo.id).label('count'),
            func.sum(OutputVideo.file_size).label('size')
        ).join(Job).group_by(Job.template_id).all()
        
        # Get disk usage
        disk_stat = os.statvfs(OUTPUT_DIR)
        disk_total = disk_stat.f_blocks * disk_stat.f_bsize
        disk_free = disk_stat.f_available * disk_stat.f_bsize
        disk_used = disk_total - disk_free
        
        return {
            "database_stats": {
                "total_files": stats.total_files or 0,
                "total_size_bytes": stats.total_size or 0,
                "total_size_gb": round((stats.total_size or 0) / 1024 / 1024 / 1024, 2),
                "average_size_mb": round((stats.avg_size or 0) / 1024 / 1024, 2)
            },
            "by_video_type": [
                {
                    "type": stat.video_type,
                    "count": stat.count,
                    "size_gb": round((stat.size or 0) / 1024 / 1024 / 1024, 2)
                }
                for stat in type_stats
            ],
            "by_template": [
                {
                    "template_id": stat.template_id,
                    "count": stat.count,
                    "size_gb": round((stat.size or 0) / 1024 / 1024 / 1024, 2)
                }
                for stat in template_stats
            ],
            "disk_usage": {
                "total_gb": round(disk_total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk_used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk_free / 1024 / 1024 / 1024, 2),
                "usage_percent": round((disk_used / disk_total) * 100, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Storage stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup/auto")
async def auto_cleanup(
    cleanup_type: str = Query(..., regex="^(age|size|failed)$"),
    params: Dict[str, Any] = {},
    dry_run: bool = True,
    db: Session = Depends(get_db)
):
    """Automatic cleanup based on criteria"""
    
    try:
        query = db.query(OutputVideo).join(Job)
        
        if cleanup_type == "age":
            days = params.get("days", 30)
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(OutputVideo.created_at < cutoff_date)
            
        elif cleanup_type == "size":
            # Clean up large individual clips
            max_size_mb = params.get("max_size_mb", 100)
            query = query.filter(
                and_(
                    OutputVideo.video_type == "individual",
                    OutputVideo.file_size > max_size_mb * 1024 * 1024
                )
            )
            
        elif cleanup_type == "failed":
            # Clean up files from failed jobs
            query = query.filter(Job.status == "failed")
        
        # Get files to delete
        files_to_delete = query.all()
        
        if dry_run:
            # Just return what would be deleted
            return {
                "dry_run": True,
                "would_delete": len(files_to_delete),
                "total_size_gb": round(
                    sum(f.file_size or 0 for f in files_to_delete) / 1024 / 1024 / 1024, 2
                ),
                "files": [
                    {
                        "id": f.id,
                        "file_path": f.file_path,
                        "size_mb": round((f.file_size or 0) / 1024 / 1024, 2),
                        "created_at": f.created_at.isoformat() if f.created_at else None
                    }
                    for f in files_to_delete[:20]  # Show first 20
                ]
            }
        
        # Actually delete files
        deleted_count = 0
        deleted_size = 0
        
        for video in files_to_delete:
            try:
                if os.path.exists(video.file_path):
                    os.remove(video.file_path)
                    deleted_size += video.file_size or 0
                
                # Log deletion
                deletion_log = FileDeletionLog(
                    job_id=video.job_id,
                    output_video_id=video.id,
                    file_path=video.file_path,
                    file_size=video.file_size,
                    deleted_by="system",
                    deletion_reason=cleanup_type
                )
                db.add(deletion_log)
                
                db.delete(video)
                deleted_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to delete {video.file_path}: {e}")
        
        db.commit()
        
        return {
            "dry_run": False,
            "deleted_count": deleted_count,
            "deleted_size_gb": round(deleted_size / 1024 / 1024 / 1024, 2),
            "cleanup_type": cleanup_type,
            "params": params
        }
        
    except Exception as e:
        logger.error(f"Auto cleanup error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deletion-logs")
async def get_deletion_logs(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    reason: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get file deletion history"""
    
    try:
        query = db.query(FileDeletionLog)
        
        if date_from:
            query = query.filter(FileDeletionLog.deleted_at >= date_from)
        if date_to:
            query = query.filter(FileDeletionLog.deleted_at <= date_to)
        if reason:
            query = query.filter(FileDeletionLog.deletion_reason == reason)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        logs = query.order_by(FileDeletionLog.deleted_at.desc()).offset(offset).limit(per_page).all()
        
        return {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "logs": [
                {
                    "id": log.id,
                    "job_id": log.job_id,
                    "file_path": log.file_path,
                    "file_size_mb": round((log.file_size or 0) / 1024 / 1024, 2),
                    "deleted_at": log.deleted_at.isoformat() if log.deleted_at else None,
                    "deleted_by": log.deleted_by,
                    "reason": log.deletion_reason,
                    "is_backed_up": log.is_backed_up,
                    "backup_location": log.backup_location
                }
                for log in logs
            ]
        }
        
    except Exception as e:
        logger.error(f"Get deletion logs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))