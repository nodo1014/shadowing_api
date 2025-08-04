"""
Database adapter for backward compatibility
Redirects old database.py calls to new modular structure
"""
from shadowing_maker.database.connection import init_database as _init_database
from shadowing_maker.database.repositories.job_repo import JobRepository

# Initialize database
def init_db():
    """Initialize database (backward compatible)"""
    return _init_database()

# Job operations
def save_job_to_db(job_data):
    """Save job to database (backward compatible)"""
    return JobRepository.create(job_data)

def update_job_status(job_id, status, progress=None, message=None, error=None, output_file=None, results=None):
    """Update job status (backward compatible)"""
    return JobRepository.update_status(
        job_id, status, progress, message, error, output_file, results
    )

def get_job_by_id(job_id):
    """Get job by ID (backward compatible)"""
    return JobRepository.get_by_id(job_id)

def delete_job(job_id):
    """Delete job (backward compatible)"""
    return JobRepository.delete(job_id)

def get_recent_jobs(limit=50):
    """Get recent jobs (backward compatible)"""
    return JobRepository.get_recent(limit)

def search_jobs(query, limit=50):
    """Search jobs (backward compatible)"""
    return JobRepository.search(query, limit)

def get_statistics():
    """Get statistics (backward compatible)"""
    return JobRepository.get_statistics()

def cleanup_old_jobs(days=30):
    """Cleanup old jobs (backward compatible)"""
    return JobRepository.cleanup_old(days)

def delete_jobs_bulk(job_ids):
    """Delete multiple jobs (backward compatible)"""
    deleted = 0
    for job_id in job_ids:
        if JobRepository.delete(job_id):
            deleted += 1
    return deleted

def get_disk_usage():
    """Get disk usage (backward compatible)"""
    from pathlib import Path
    output_dir = Path("./output")
    
    if not output_dir.exists():
        return {"total_size": 0, "file_count": 0}
    
    total_size = 0
    file_count = 0
    
    for file in output_dir.rglob("*"):
        if file.is_file():
            total_size += file.stat().st_size
            file_count += 1
    
    return {
        "total_size": total_size,
        "file_count": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2)
    }