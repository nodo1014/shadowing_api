"""
Database models and operations for Video Clipping API
"""

from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Text, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clipping.db")

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base model
Base = declarative_base()


class ClippingJob(Base):
    """클리핑 작업 정보"""
    __tablename__ = "clipping_jobs"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)  # Status message
    error_message = Column(Text, nullable=True)
    
    # Media info
    media_path = Column(String)
    media_filename = Column(String)
    
    # Clipping info
    clipping_type = Column(Integer)
    start_time = Column(Float)
    end_time = Column(Float)
    duration = Column(Float)
    
    # Subtitle info
    text_eng = Column(Text)
    text_kor = Column(Text)
    note = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)  # Store as JSON array
    
    # Output info
    output_file = Column(String, nullable=True)
    output_size = Column(Integer, nullable=True)  # File size in bytes
    individual_clips = Column(JSON, nullable=True)  # Store paths as JSON
    
    # User info (for future use)
    user_id = Column(String, nullable=True)
    client_ip = Column(String, nullable=True)


class BatchJob(Base):
    """배치 작업 정보"""
    __tablename__ = "batch_jobs"
    
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Status
    status = Column(String, default="pending")
    progress = Column(Integer, default=0)
    total_clips = Column(Integer)
    completed_clips = Column(Integer, default=0)
    
    # Media info
    media_path = Column(String)
    clipping_type = Column(Integer)
    
    # Output info
    output_files = Column(JSON)  # List of clip info
    
    # User info
    user_id = Column(String, nullable=True)
    client_ip = Column(String, nullable=True)


# Database operations
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def save_job_to_db(job_id: str, job_data: dict):
    """Save job information to database"""
    db = SessionLocal()
    try:
        job = ClippingJob(
            id=job_id,
            status=job_data.get("status", "pending"),
            progress=job_data.get("progress", 0),
            media_path=job_data.get("media_path"),
            media_filename=os.path.basename(job_data.get("media_path", "")),
            clipping_type=job_data.get("clipping_type"),
            start_time=job_data.get("start_time"),
            end_time=job_data.get("end_time"),
            duration=job_data.get("end_time", 0) - job_data.get("start_time", 0),
            text_eng=job_data.get("text_eng"),
            text_kor=job_data.get("text_kor"),
            note=job_data.get("note"),
            keywords=job_data.get("keywords"),
            output_file=job_data.get("output_file"),
            individual_clips=job_data.get("individual_clips"),
            client_ip=job_data.get("client_ip")
        )
        db.add(job)
        db.commit()
        return job
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def update_job_status(job_id: str, status: str, progress: int = None, 
                     output_file: str = None, error_message: str = None, message: str = None):
    """Update job status in database"""
    db = SessionLocal()
    try:
        job = db.query(ClippingJob).filter(ClippingJob.id == job_id).first()
        if job:
            job.status = status
            if progress is not None:
                job.progress = progress
            if output_file:
                job.output_file = output_file
                # Get file size
                if os.path.exists(output_file):
                    job.output_size = os.path.getsize(output_file)
            if error_message:
                job.error_message = error_message
            if message:
                job.message = message
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def get_job_by_id(job_id: str):
    """Get job information by ID"""
    db = SessionLocal()
    try:
        return db.query(ClippingJob).filter(ClippingJob.id == job_id).first()
    finally:
        db.close()


def get_recent_jobs(limit: int = 20, user_id: str = None):
    """Get recent jobs"""
    db = SessionLocal()
    try:
        query = db.query(ClippingJob)
        if user_id:
            query = query.filter(ClippingJob.user_id == user_id)
        return query.order_by(ClippingJob.created_at.desc()).limit(limit).all()
    finally:
        db.close()


def search_jobs(keyword: str = None, status: str = None, 
                start_date: datetime = None, end_date: datetime = None):
    """Search jobs with filters"""
    db = SessionLocal()
    try:
        query = db.query(ClippingJob)
        
        if keyword:
            query = query.filter(
                (ClippingJob.text_eng.contains(keyword)) |
                (ClippingJob.text_kor.contains(keyword)) |
                (ClippingJob.media_filename.contains(keyword))
            )
        
        if status:
            query = query.filter(ClippingJob.status == status)
            
        if start_date:
            query = query.filter(ClippingJob.created_at >= start_date)
            
        if end_date:
            query = query.filter(ClippingJob.created_at <= end_date)
            
        return query.order_by(ClippingJob.created_at.desc()).all()
    finally:
        db.close()


def get_statistics():
    """Get usage statistics"""
    db = SessionLocal()
    try:
        total_jobs = db.query(ClippingJob).count()
        completed_jobs = db.query(ClippingJob).filter(ClippingJob.status == "completed").count()
        failed_jobs = db.query(ClippingJob).filter(ClippingJob.status == "failed").count()
        
        # Total duration processed
        from sqlalchemy import func
        total_duration = db.query(func.sum(ClippingJob.duration)).filter(
            ClippingJob.status == "completed"
        ).scalar() or 0
        
        # Total output size
        total_size = db.query(func.sum(ClippingJob.output_size)).filter(
            ClippingJob.status == "completed"
        ).scalar() or 0
        
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "total_duration_seconds": total_duration,
            "total_output_size_mb": total_size / (1024 * 1024) if total_size else 0
        }
    finally:
        db.close()


def delete_job(job_id: str, delete_files: bool = True):
    """Delete job and optionally its files"""
    db = SessionLocal()
    try:
        job = db.query(ClippingJob).filter(ClippingJob.id == job_id).first()
        if not job:
            return False
            
        # Delete files if requested
        if delete_files and job.output_file:
            import shutil
            from pathlib import Path
            
            # Delete output directory
            output_dir = Path(job.output_file).parent
            if output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)
        
        # Delete from database
        db.delete(job)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def delete_jobs_bulk(job_ids: list, delete_files: bool = True):
    """Delete multiple jobs"""
    deleted_count = 0
    for job_id in job_ids:
        if delete_job(job_id, delete_files):
            deleted_count += 1
    return deleted_count


def cleanup_old_jobs(days_old: int = 30, delete_files: bool = True):
    """Delete jobs older than specified days"""
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_jobs = db.query(ClippingJob).filter(
            ClippingJob.created_at < cutoff_date
        ).all()
        
        job_ids = [job.id for job in old_jobs]
        return delete_jobs_bulk(job_ids, delete_files)
    finally:
        db.close()


def get_disk_usage():
    """Get disk usage statistics"""
    db = SessionLocal()
    try:
        # Get total size by status
        from sqlalchemy import func
        
        usage_by_status = db.query(
            ClippingJob.status,
            func.sum(ClippingJob.output_size).label('total_size'),
            func.count(ClippingJob.id).label('count')
        ).group_by(ClippingJob.status).all()
        
        # Get top 10 largest outputs
        largest_outputs = db.query(ClippingJob).filter(
            ClippingJob.output_size.isnot(None)
        ).order_by(ClippingJob.output_size.desc()).limit(10).all()
        
        return {
            "by_status": [
                {
                    "status": item.status,
                    "total_size_mb": (item.total_size or 0) / (1024 * 1024),
                    "count": item.count
                }
                for item in usage_by_status
            ],
            "largest_outputs": [
                {
                    "id": job.id,
                    "filename": job.media_filename,
                    "size_mb": job.output_size / (1024 * 1024),
                    "created_at": job.created_at
                }
                for job in largest_outputs
            ]
        }
    finally:
        db.close()


# Initialize database when module is imported
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")