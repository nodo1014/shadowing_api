"""
Job Management Utilities
"""
import os
import psutil
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
import sys

# Add parent directory to path for database imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# Job status storage (will be initialized by main app)
job_status = {}
active_processes = {}
redis_client = None
USE_REDIS = False
MAX_JOB_MEMORY = 1000
JOB_EXPIRE_TIME = 86400


def set_redis_client(client, use_redis: bool):
    """Redis 클라이언트 설정"""
    global redis_client, USE_REDIS
    redis_client = client
    USE_REDIS = use_redis


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
    if job_id not in job_status:
        job_status[job_id] = {
            'job_id': job_id,
            'status': status,
            'progress': 0,
            'message': '',
            'created_at': datetime.now().isoformat(),
        }
    
    job_data = job_status[job_id]
    
    # 기존 데이터 보존 (output_files 등)
    existing_output_files = job_data.get('output_files')
    
    job_data['status'] = status
    job_data['updated_at'] = datetime.now().isoformat()
    
    if progress is not None:
        job_data['progress'] = progress
    if message is not None:
        job_data['message'] = message
    if output_file is not None:
        job_data['output_file'] = output_file
    if error_message is not None:
        job_data['error'] = error_message
    
    # output_files가 있었다면 보존
    if existing_output_files is not None:
        job_data['output_files'] = existing_output_files
    
    # DB 업데이트 비활성화 - 메모리만 사용
    
    # Redis 업데이트 (모든 worker에서 접근 가능)
    if USE_REDIS and redis_client:
        try:
            import pickle
            redis_client.setex(
                f"job_status:{job_id}",
                JOB_EXPIRE_TIME,
                pickle.dumps(job_data)
            )
        except Exception as e:
            logger.warning(f"Redis update failed: {e}")
    
    # 메모리 정리
    cleanup_memory_jobs()
    
    # 완료/실패 시 프로세스 정리
    if status in ['completed', 'failed']:
        cleanup_job_processes(job_id)
        
        # 출력 파일 경로 업데이트 (웹 접근 가능한 경로로 변환)
        if output_file and os.path.exists(output_file):
            try:
                # 절대 경로를 상대 경로로 변환
                output_path = Path(output_file).resolve()
                base_path = Path.cwd()
                relative_path = output_path.relative_to(base_path)
                job_data['output_file'] = str(relative_path).replace('\\', '/')
                
                # individual_clips 디렉토리 확인
                individual_clips_dir = output_path.parent / "individual_clips"
                if individual_clips_dir.exists() and individual_clips_dir.is_dir():
                    job_data['individual_clips_dir'] = str(
                        individual_clips_dir.relative_to(base_path)
                    ).replace('\\', '/')
                    
                    # 개별 클립 파일 목록 추가
                    clips = []
                    for clip_file in sorted(individual_clips_dir.rglob("*.mp4")):
                        clips.append(str(clip_file.relative_to(base_path)).replace('\\', '/'))
                    if clips:
                        job_data['individual_clips'] = clips
                        
                        # 새 DB에도 개별 클립 정보 업데이트
                        try:
                            from database_v2.models_v2 import DatabaseManager, Job
                            with DatabaseManager.get_session() as session:
                                job = session.query(Job).filter_by(id=job_id).first()
                                if job:
                                    job.extra_data = job.extra_data or {}
                                    job.extra_data['individual_clips'] = clips
                                    session.commit()
                        except Exception as db_err:
                            logger.warning(f"Failed to update individual clips in DB: {db_err}")
                        
            except Exception as e:
                logger.warning(f"Failed to convert path: {e}")


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """작업 상태 조회 (메모리, Redis 또는 새 DB에서)"""
    # 먼저 메모리에서 확인
    if job_id in job_status:
        return job_status[job_id]
    
    # Redis에서 확인
    if USE_REDIS and redis_client:
        try:
            import pickle
            data = redis_client.get(f"job_status:{job_id}")
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.warning(f"Redis read failed: {e}")
    
    # 새 DB에서 확인
    try:
        from database_v2.models_v2 import DatabaseManager, Job
        with DatabaseManager.get_session() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                # DB 데이터를 기존 형식으로 변환
                return {
                    'job_id': job.id,
                    'status': job.status,
                    'progress': job.progress,
                    'message': job.message,
                    'error': job.error_message,
                    'output_file': None,  # output_videos 테이블에서 가져와야 함
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'updated_at': job.updated_at.isoformat() if job.updated_at else None,
                    'media_path': job.request_body.get('media_path') if isinstance(job.request_body, dict) else None,
                    'template_number': job.template_id,
                    'start_time': job.start_time,
                    'end_time': job.end_time
                }
    except Exception as e:
        logger.warning(f"DB read failed for job {job_id}: {e}")
    
    return None