"""
Process management and cleanup utilities
프로세스 관리 및 정리 유틸리티
"""
import asyncio
import logging
import psutil
import signal
from typing import Dict, Optional
from datetime import datetime, timedelta
import subprocess

logger = logging.getLogger(__name__)

class ProcessManager:
    """프로세스 생명주기 관리"""
    
    def __init__(self, max_processes: int = 10, timeout: int = 300):
        self.max_processes = max_processes
        self.timeout = timeout
        self.active_processes: Dict[str, Dict] = {}
        self._cleanup_task = None
        
    async def start(self):
        """프로세스 매니저 시작"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info(f"ProcessManager started with max_processes={self.max_processes}")
        
    async def stop(self):
        """프로세스 매니저 종료"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        # 모든 활성 프로세스 종료
        await self.terminate_all()
        logger.info("ProcessManager stopped")
        
    async def add_process(self, job_id: str, process: subprocess.Popen, 
                         description: str = "Unknown task") -> bool:
        """프로세스 추가"""
        if len(self.active_processes) >= self.max_processes:
            logger.warning(f"Max processes limit reached ({self.max_processes})")
            return False
            
        self.active_processes[job_id] = {
            "process": process,
            "pid": process.pid,
            "start_time": datetime.utcnow(),
            "description": description
        }
        logger.info(f"Added process {process.pid} for job {job_id}: {description}")
        return True
        
    async def remove_process(self, job_id: str) -> bool:
        """프로세스 제거"""
        if job_id in self.active_processes:
            info = self.active_processes.pop(job_id)
            logger.info(f"Removed process {info['pid']} for job {job_id}")
            return True
        return False
        
    async def terminate_process(self, job_id: str, force: bool = False) -> bool:
        """프로세스 종료"""
        if job_id not in self.active_processes:
            return False
            
        proc_info = self.active_processes[job_id]
        process = proc_info["process"]
        
        try:
            if process.poll() is None:  # 프로세스가 아직 실행 중
                if force:
                    process.kill()
                    logger.warning(f"Force killed process {proc_info['pid']} for job {job_id}")
                else:
                    process.terminate()
                    logger.info(f"Terminated process {proc_info['pid']} for job {job_id}")
                    
                # 프로세스 종료 대기 (최대 5초)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.warning(f"Had to kill process {proc_info['pid']} after timeout")
                    
            await self.remove_process(job_id)
            return True
            
        except Exception as e:
            logger.error(f"Error terminating process for job {job_id}: {e}")
            return False
            
    async def terminate_all(self):
        """모든 프로세스 종료"""
        job_ids = list(self.active_processes.keys())
        for job_id in job_ids:
            await self.terminate_process(job_id, force=True)
            
    async def _periodic_cleanup(self):
        """주기적으로 오래된/좀비 프로세스 정리"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 실행
                await self._cleanup_stale_processes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                
    async def _cleanup_stale_processes(self):
        """오래되거나 종료된 프로세스 정리"""
        current_time = datetime.utcnow()
        to_remove = []
        
        for job_id, info in self.active_processes.items():
            process = info["process"]
            start_time = info["start_time"]
            
            # 프로세스가 이미 종료됨
            if process.poll() is not None:
                to_remove.append(job_id)
                logger.info(f"Found terminated process for job {job_id}")
                continue
                
            # 타임아웃 초과
            if (current_time - start_time).total_seconds() > self.timeout:
                logger.warning(f"Process timeout for job {job_id}, terminating...")
                await self.terminate_process(job_id, force=True)
                to_remove.append(job_id)
                continue
                
            # 좀비 프로세스 확인
            try:
                proc = psutil.Process(info["pid"])
                if proc.status() == psutil.STATUS_ZOMBIE:
                    to_remove.append(job_id)
                    logger.warning(f"Found zombie process for job {job_id}")
            except psutil.NoSuchProcess:
                to_remove.append(job_id)
                logger.warning(f"Process {info['pid']} no longer exists for job {job_id}")
                
        # 정리
        for job_id in to_remove:
            await self.remove_process(job_id)
            
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} stale processes")
            
    def get_status(self) -> Dict:
        """프로세스 매니저 상태 반환"""
        return {
            "active_processes": len(self.active_processes),
            "max_processes": self.max_processes,
            "processes": [
                {
                    "job_id": job_id,
                    "pid": info["pid"],
                    "description": info["description"],
                    "runtime_seconds": (datetime.utcnow() - info["start_time"]).total_seconds(),
                    "status": "running" if info["process"].poll() is None else "terminated"
                }
                for job_id, info in self.active_processes.items()
            ]
        }
        
    def is_process_running(self, job_id: str) -> bool:
        """프로세스 실행 중인지 확인"""
        if job_id not in self.active_processes:
            return False
            
        process = self.active_processes[job_id]["process"]
        return process.poll() is None