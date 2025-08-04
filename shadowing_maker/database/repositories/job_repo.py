"""
Job repository for database operations
"""
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from ..connection import execute_query, execute_update, execute_insert

logger = logging.getLogger(__name__)


class JobRepository:
    """Repository for job-related database operations"""
    
    @staticmethod
    def create(job_data: Dict[str, Any]) -> bool:
        """Create a new job"""
        try:
            # Convert lists/dicts to JSON strings
            if 'keywords' in job_data and isinstance(job_data['keywords'], list):
                job_data['keywords'] = json.dumps(job_data['keywords'])
            if 'results' in job_data and isinstance(job_data['results'], (list, dict)):
                job_data['results'] = json.dumps(job_data['results'])
            if 'clips' in job_data and isinstance(job_data['clips'], list):
                job_data['clips'] = json.dumps(job_data['clips'])
            
            columns = ', '.join(job_data.keys())
            placeholders = ', '.join(['?' for _ in job_data])
            
            query = f"INSERT INTO jobs ({columns}) VALUES ({placeholders})"
            execute_update(query, tuple(job_data.values()))
            
            logger.info(f"Job created: {job_data.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return False
    
    @staticmethod
    def get_by_id(job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        try:
            query = "SELECT * FROM jobs WHERE id = ?"
            results = execute_query(query, (job_id,))
            
            if results:
                job = results[0]
                # Parse JSON fields
                if job.get('keywords'):
                    try:
                        job['keywords'] = json.loads(job['keywords'])
                    except:
                        pass
                if job.get('results'):
                    try:
                        job['results'] = json.loads(job['results'])
                    except:
                        pass
                if job.get('clips'):
                    try:
                        job['clips'] = json.loads(job['clips'])
                    except:
                        pass
                return job
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    @staticmethod
    def update_status(
        job_id: str,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        output_file: Optional[str] = None,
        results: Optional[Any] = None
    ) -> bool:
        """Update job status"""
        try:
            updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            
            if message is not None:
                updates.append("message = ?")
                params.append(message)
            
            if error is not None:
                updates.append("error = ?")
                params.append(error)
            
            if output_file is not None:
                updates.append("output_file = ?")
                params.append(output_file)
            
            if results is not None:
                updates.append("results = ?")
                params.append(json.dumps(results) if isinstance(results, (list, dict)) else results)
            
            if status == "completed":
                updates.append("completed_at = CURRENT_TIMESTAMP")
            
            params.append(job_id)
            
            query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
            rows = execute_update(query, tuple(params))
            
            if rows > 0:
                logger.info(f"Job {job_id} status updated to {status}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
    
    @staticmethod
    def delete(job_id: str) -> bool:
        """Delete a job"""
        try:
            query = "DELETE FROM jobs WHERE id = ?"
            rows = execute_update(query, (job_id,))
            
            if rows > 0:
                logger.info(f"Job {job_id} deleted")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False
    
    @staticmethod
    def get_recent(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent jobs"""
        try:
            if status:
                query = "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?"
                params = (status, limit)
            else:
                query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?"
                params = (limit,)
            
            results = execute_query(query, params)
            
            # Parse JSON fields
            for job in results:
                if job.get('keywords'):
                    try:
                        job['keywords'] = json.loads(job['keywords'])
                    except:
                        pass
                if job.get('results'):
                    try:
                        job['results'] = json.loads(job['results'])
                    except:
                        pass
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get recent jobs: {e}")
            return []
    
    @staticmethod
    def search(query_text: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search jobs"""
        try:
            query = """
                SELECT * FROM jobs 
                WHERE text_eng LIKE ? 
                   OR text_kor LIKE ? 
                   OR note LIKE ?
                   OR media_path LIKE ?
                   OR id LIKE ?
                ORDER BY created_at DESC 
                LIMIT ?
            """
            search_term = f"%{query_text}%"
            params = (search_term, search_term, search_term, search_term, search_term, limit)
            
            results = execute_query(query, params)
            
            # Parse JSON fields
            for job in results:
                if job.get('keywords'):
                    try:
                        job['keywords'] = json.loads(job['keywords'])
                    except:
                        pass
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search jobs: {e}")
            return []
    
    @staticmethod
    def cleanup_old(days: int = 30) -> int:
        """Delete jobs older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = "DELETE FROM jobs WHERE created_at < ?"
            rows = execute_update(query, (cutoff_date.isoformat(),))
            
            logger.info(f"Deleted {rows} old jobs")
            return rows
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get job statistics"""
        try:
            stats = {}
            
            # Total jobs
            query = "SELECT COUNT(*) as total FROM jobs"
            result = execute_query(query)
            stats['total_jobs'] = result[0]['total'] if result else 0
            
            # Jobs by status
            query = "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
            results = execute_query(query)
            stats['by_status'] = {row['status']: row['count'] for row in results}
            
            # Jobs today
            query = "SELECT COUNT(*) as count FROM jobs WHERE DATE(created_at) = DATE('now')"
            result = execute_query(query)
            stats['today'] = result[0]['count'] if result else 0
            
            # Jobs this week
            query = "SELECT COUNT(*) as count FROM jobs WHERE created_at >= DATE('now', '-7 days')"
            result = execute_query(query)
            stats['this_week'] = result[0]['count'] if result else 0
            
            # Jobs by type
            query = "SELECT type, COUNT(*) as count FROM jobs GROUP BY type"
            results = execute_query(query)
            stats['by_type'] = {row['type']: row['count'] for row in results}
            
            # Average processing time (completed jobs)
            query = """
                SELECT AVG(
                    CAST((julianday(completed_at) - julianday(created_at)) * 24 * 60 * 60 AS REAL)
                ) as avg_time 
                FROM jobs 
                WHERE status = 'completed' AND completed_at IS NOT NULL
            """
            result = execute_query(query)
            stats['avg_processing_time'] = result[0]['avg_time'] if result and result[0]['avg_time'] else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}