"""
Enhanced Batch Renderer with GPU acceleration and advanced monitoring
고급 모니터링 및 GPU 가속을 지원하는 향상된 배치 렌더러
"""
import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import psutil
import queue
from enum import Enum
import pickle

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """작업 우선순위"""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class JobStatus(Enum):
    """작업 상태"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """배치 작업 정보"""
    job_id: str
    priority: JobPriority
    clips: List[Dict]
    media_path: str
    template_name: str
    output_dir: Path
    created_at: datetime = field(default_factory=datetime.now)
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    total_clips: int = 0
    completed_clips: int = 0
    failed_clips: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_messages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """우선순위 비교 (priority queue용)"""
        return self.priority.value < other.priority.value


class GPUDetector:
    """GPU 검출 및 FFmpeg GPU 옵션 관리"""
    
    @staticmethod
    def detect_nvidia_gpu() -> bool:
        """NVIDIA GPU 사용 가능 여부 확인"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def detect_amd_gpu() -> bool:
        """AMD GPU 사용 가능 여부 확인"""
        try:
            import subprocess
            result = subprocess.run(['rocm-smi'], capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def get_gpu_encoding_options() -> Dict[str, Any]:
        """GPU 인코딩 옵션 반환"""
        if GPUDetector.detect_nvidia_gpu():
            return {
                'encoder': 'h264_nvenc',
                'decoder': 'h264_cuvid',
                'options': [
                    '-rc', 'vbr',
                    '-cq', '19',
                    '-preset', 'p4',
                    '-b:v', '0',
                    '-profile:v', 'high'
                ]
            }
        elif GPUDetector.detect_amd_gpu():
            return {
                'encoder': 'h264_amf',
                'decoder': None,
                'options': [
                    '-quality', 'balanced',
                    '-rc', 'vbr_peak',
                    '-b:v', '8M'
                ]
            }
        else:
            return {
                'encoder': 'libx264',
                'decoder': None,
                'options': [
                    '-preset', 'medium',
                    '-crf', '22',
                    '-profile:v', 'high',
                    '-level', '4.1',
                    '-tune', 'film'
                ]
            }


class EnhancedBatchRenderer:
    """향상된 배치 렌더러"""
    
    def __init__(self, 
                 max_workers: int = 4,
                 use_gpu: bool = True,
                 checkpoint_dir: Path = Path("./batch_checkpoints"),
                 stats_callback: Optional[Callable] = None):
        self.max_workers = max_workers
        self.use_gpu = use_gpu
        self.checkpoint_dir = checkpoint_dir
        self.stats_callback = stats_callback
        
        # GPU 옵션 설정
        self.gpu_options = GPUDetector.get_gpu_encoding_options() if use_gpu else None
        
        # 작업 큐 및 실행 관리
        self.job_queue = asyncio.PriorityQueue()
        self.active_jobs: Dict[str, BatchJob] = {}
        self.completed_jobs: Dict[str, BatchJob] = {}
        
        # 리소스 모니터링
        self.resource_monitor = ResourceMonitor()
        
        # 체크포인트 디렉토리 생성
        checkpoint_dir.mkdir(exist_ok=True)
        
        # 실행 상태
        self._running = False
        self._workers = []
        
    async def start(self):
        """렌더러 시작"""
        self._running = True
        
        # 워커 시작
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        # 리소스 모니터 시작
        asyncio.create_task(self._monitor_resources())
        
        logger.info(f"Enhanced Batch Renderer started with {self.max_workers} workers")
        if self.gpu_options:
            logger.info(f"GPU encoding enabled: {self.gpu_options['encoder']}")
    
    async def stop(self):
        """렌더러 중지"""
        self._running = False
        
        # 모든 워커 종료 대기
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        # 체크포인트 저장
        await self._save_checkpoint()
        
        logger.info("Enhanced Batch Renderer stopped")
    
    async def submit_job(self, job: BatchJob) -> str:
        """작업 제출"""
        job.total_clips = len(job.clips)
        await self.job_queue.put(job)
        self.active_jobs[job.job_id] = job
        
        logger.info(f"Job {job.job_id} submitted with priority {job.priority.name}")
        return job.job_id
    
    async def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        """작업 상태 조회"""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        elif job_id in self.completed_jobs:
            return self.completed_jobs[job_id]
        return None
    
    async def pause_job(self, job_id: str) -> bool:
        """작업 일시정지"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            if job.status == JobStatus.PROCESSING:
                job.status = JobStatus.PAUSED
                await self._save_job_checkpoint(job)
                logger.info(f"Job {job_id} paused")
                return True
        return False
    
    async def resume_job(self, job_id: str) -> bool:
        """작업 재개"""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.checkpoint"
        if checkpoint_file.exists():
            job = await self._load_job_checkpoint(job_id)
            if job:
                job.status = JobStatus.QUEUED
                await self.submit_job(job)
                logger.info(f"Job {job_id} resumed")
                return True
        return False
    
    async def _worker(self, worker_id: int):
        """워커 프로세스"""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # 큐에서 작업 가져오기 (1초 타임아웃)
                job = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                
                # 작업 처리
                await self._process_job(job, worker_id)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_job(self, job: BatchJob, worker_id: int):
        """작업 처리"""
        logger.info(f"Worker {worker_id} processing job {job.job_id}")
        
        job.status = JobStatus.PROCESSING
        job.start_time = datetime.now()
        
        try:
            # 템플릿 인코더 로드
            from template_video_encoder import TemplateVideoEncoder
            encoder = TemplateVideoEncoder()
            
            # 체크포인트에서 시작 위치 확인
            start_from = job.completed_clips
            
            # 클립 처리
            for idx in range(start_from, len(job.clips)):
                if not self._running or job.status == JobStatus.PAUSED:
                    break
                
                clip_data = job.clips[idx]
                clip_num = idx + 1
                
                # 리소스 체크
                if not await self.resource_monitor.check_resources():
                    logger.warning("Resource limit reached, waiting...")
                    await asyncio.sleep(5)
                    continue
                
                # 클립 렌더링
                success = await self._render_clip(
                    encoder, job, clip_data, clip_num
                )
                
                if success:
                    job.completed_clips += 1
                else:
                    job.failed_clips += 1
                    job.error_messages.append(f"Clip {clip_num} failed")
                
                # 진행률 업데이트
                job.progress = (job.completed_clips / job.total_clips) * 100
                
                # 통계 콜백
                if self.stats_callback:
                    await self.stats_callback(job)
                
                # 주기적 체크포인트
                if job.completed_clips % 5 == 0:
                    await self._save_job_checkpoint(job)
            
            # 작업 완료 처리
            job.end_time = datetime.now()
            if job.completed_clips == job.total_clips:
                job.status = JobStatus.COMPLETED
            elif job.completed_clips > 0:
                job.status = JobStatus.COMPLETED  # 부분 완료
            else:
                job.status = JobStatus.FAILED
            
            # 완료된 작업으로 이동
            self.completed_jobs[job.job_id] = job
            del self.active_jobs[job.job_id]
            
            # 체크포인트 삭제
            checkpoint_file = self.checkpoint_dir / f"{job.job_id}.checkpoint"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            
            logger.info(f"Job {job.job_id} completed: {job.completed_clips}/{job.total_clips}")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_messages.append(str(e))
            job.end_time = datetime.now()
    
    async def _render_clip(self, encoder, job: BatchJob, clip_data: Dict, 
                          clip_num: int) -> bool:
        """단일 클립 렌더링"""
        try:
            # 출력 경로 설정
            clip_dir = job.output_dir / f"clip_{clip_num:04d}"
            clip_dir.mkdir(parents=True, exist_ok=True)
            output_path = clip_dir / f"clip_{clip_num:04d}.mp4"
            
            # GPU 옵션 적용
            if self.gpu_options and hasattr(encoder, '_gpu_options'):
                encoder._gpu_options = self.gpu_options
            
            # 자막 데이터 준비
            subtitle_data = {
                'english': clip_data.get('text_eng', ''),
                'korean': clip_data.get('text_kor', ''),
                'start_time': 0,
                'end_time': clip_data['end_time'] - clip_data['start_time'],
                'keywords': clip_data.get('keywords', [])
            }
            
            # 비동기 실행을 위한 executor 사용
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                encoder.create_from_template,
                job.template_name,
                job.media_path,
                subtitle_data,
                str(output_path),
                clip_data['start_time'],
                clip_data['end_time'],
                0.5,  # padding_before
                0.5,  # padding_after
                True  # save_individual_clips
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Clip {clip_num} rendering error: {e}")
            return False
    
    async def _monitor_resources(self):
        """리소스 모니터링"""
        while self._running:
            try:
                stats = self.resource_monitor.get_current_stats()
                
                # 리소스 임계치 초과시 경고
                if stats['memory_percent'] > 90:
                    logger.warning(f"High memory usage: {stats['memory_percent']}%")
                
                if stats['cpu_percent'] > 95:
                    logger.warning(f"High CPU usage: {stats['cpu_percent']}%")
                
                # 통계 로깅 (5분마다)
                if int(time.time()) % 300 == 0:
                    logger.info(f"System resources - CPU: {stats['cpu_percent']}%, "
                              f"Memory: {stats['memory_percent']}%, "
                              f"Disk: {stats['disk_free_gb']:.1f}GB free")
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _save_checkpoint(self):
        """전체 상태 체크포인트 저장"""
        checkpoint_data = {
            'active_jobs': list(self.active_jobs.values()),
            'completed_jobs': list(self.completed_jobs.values()),
            'timestamp': datetime.now()
        }
        
        checkpoint_file = self.checkpoint_dir / "renderer_state.checkpoint"
        with open(checkpoint_file, 'wb') as f:
            pickle.dump(checkpoint_data, f)
    
    async def _save_job_checkpoint(self, job: BatchJob):
        """개별 작업 체크포인트 저장"""
        checkpoint_file = self.checkpoint_dir / f"{job.job_id}.checkpoint"
        with open(checkpoint_file, 'wb') as f:
            pickle.dump(job, f)
    
    async def _load_job_checkpoint(self, job_id: str) -> Optional[BatchJob]:
        """작업 체크포인트 로드"""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.checkpoint"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'rb') as f:
                return pickle.load(f)
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """렌더러 통계 반환"""
        total_jobs = len(self.active_jobs) + len(self.completed_jobs)
        completed_clips = sum(job.completed_clips for job in self.completed_jobs.values())
        failed_clips = sum(job.failed_clips for job in self.completed_jobs.values())
        
        return {
            'total_jobs': total_jobs,
            'active_jobs': len(self.active_jobs),
            'completed_jobs': len(self.completed_jobs),
            'total_clips_processed': completed_clips,
            'total_clips_failed': failed_clips,
            'success_rate': (completed_clips / (completed_clips + failed_clips) * 100) 
                           if completed_clips + failed_clips > 0 else 0,
            'gpu_enabled': self.gpu_options is not None,
            'workers': self.max_workers
        }
    
    def create_batch_video(self, video_files: List[str], output_path: str, 
                          title_1: str = None, title_2: str = None) -> bool:
        """개별 비디오 파일들을 하나의 배치 비디오로 결합"""
        import subprocess
        import tempfile
        import os
        
        try:
            if not video_files:
                logger.error("No video files provided for batch")
                return False
            
            logger.info(f"Creating batch video with {len(video_files)} clips")
            
            # 먼저 비디오 파일들의 코덱 정보를 확인
            first_video_info = self._get_video_info(video_files[0])
            if not first_video_info:
                logger.error("Failed to get video info for first clip")
                return False
            
            # concat 파일 생성 - 정확한 duration 포함
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for i, video_file in enumerate(video_files):
                    if not os.path.exists(video_file):
                        logger.error(f"Video file not found: {video_file}")
                        return False
                    # FFmpeg concat demuxer 형식
                    f.write(f"file '{os.path.abspath(video_file)}'\n")
                    
                    # 각 클립의 duration 확인 (디버깅용)
                    video_info = self._get_video_info(video_file)
                    if video_info and 'format' in video_info:
                        duration = video_info['format'].get('duration', 'unknown')
                        logger.info(f"Clip {i+1}: {os.path.basename(video_file)} - duration: {duration}s")
                concat_file = f.name
            
            try:
                # 먼저 concat demuxer를 시도하되, vsync와 async 옵션 추가
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file,
                    # 비디오 설정
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '16',  # 높은 품질
                    '-profile:v', 'high',
                    '-level', '4.1',
                    '-pix_fmt', 'yuv420p',
                    # 해상도는 원본 유지 (고정하지 않음)
                    '-r', '30',  # 프레임레이트 고정
                    '-vsync', 'cfr',  # 일정한 프레임레이트 강제
                    '-g', '60',  # 키프레임 간격
                    '-bf', '2',  # B-프레임
                    # 오디오 설정
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '48000',
                    '-ac', '2',  # 스테레오
                    # 추가 설정
                    '-movflags', '+faststart',
                    '-max_muxing_queue_size', '1024',
                    '-avoid_negative_ts', 'make_zero',  # 타임스탬프 문제 해결
                    '-fflags', '+genpts+igndts',  # PTS 생성, DTS 무시
                    '-threads', '0',  # 자동 스레드
                    output_path
                ]
                
                logger.info(f"Running FFmpeg concat with re-encoding for {len(video_files)} files")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"FFmpeg concat error: {result.stderr}")
                    
                    # 대체 방법: filter_complex 사용
                    logger.info("Trying alternative method with filter_complex")
                    
                    # 각 입력 파일에 대한 -i 옵션 생성
                    input_args = []
                    filter_parts = []
                    for i, video_file in enumerate(video_files):
                        input_args.extend(['-i', video_file])
                        filter_parts.append(f'[{i}:v] [{i}:a] ')
                    
                    # filter_complex 구성
                    filter_complex = ''.join(filter_parts) + f'concat=n={len(video_files)}:v=1:a=1 [v] [a]'
                    
                    cmd = ['ffmpeg', '-y']
                    cmd.extend(input_args)
                    cmd.extend([
                        '-filter_complex', filter_complex,
                        '-map', '[v]',
                        '-map', '[a]',
                        '-c:v', 'libx264',
                        '-preset', 'medium',
                        '-crf', '16',
                        '-profile:v', 'high',
                        '-level', '4.1',
                        '-pix_fmt', 'yuv420p',
                        # 해상도는 원본 유지 (고정하지 않음)
                        '-r', '30',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-ar', '48000',
                        '-movflags', '+faststart',
                        output_path
                    ])
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.error(f"FFmpeg filter_complex error: {result.stderr}")
                        return False
                
                logger.info(f"Batch video created successfully: {output_path}")
                return True
                
            finally:
                # 임시 파일 삭제
                if os.path.exists(concat_file):
                    os.unlink(concat_file)
            
        except Exception as e:
            logger.error(f"Error creating batch video: {e}")
            return False
    
    def _get_video_info(self, video_path: str) -> dict:
        """비디오 정보 추출"""
        import subprocess
        import json
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"ffprobe error: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None


class ResourceMonitor:
    """시스템 리소스 모니터"""
    
    def __init__(self, max_memory_percent: float = 85.0, 
                 min_disk_gb: float = 5.0):
        self.max_memory_percent = max_memory_percent
        self.min_disk_gb = min_disk_gb
    
    async def check_resources(self) -> bool:
        """리소스 사용 가능 여부 확인"""
        stats = self.get_current_stats()
        
        if stats['memory_percent'] > self.max_memory_percent:
            return False
        
        if stats['disk_free_gb'] < self.min_disk_gb:
            return False
        
        return True
    
    def get_current_stats(self) -> Dict[str, Any]:
        """현재 리소스 상태 반환"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_free_gb': disk.free / (1024**3),
            'disk_percent': disk.percent
        }


# 사용 예시
async def main():
    """배치 렌더러 사용 예시"""
    
    # 진행 상태 콜백
    async def progress_callback(job: BatchJob):
        print(f"Job {job.job_id}: {job.progress:.1f}% "
              f"({job.completed_clips}/{job.total_clips})")
    
    # 렌더러 생성
    renderer = EnhancedBatchRenderer(
        max_workers=4,
        use_gpu=True,
        stats_callback=progress_callback
    )
    
    # 렌더러 시작
    await renderer.start()
    
    # 작업 제출
    job = BatchJob(
        job_id="test_job_001",
        priority=JobPriority.HIGH,
        clips=[
            {
                'start_time': 10.0,
                'end_time': 15.0,
                'text_eng': 'Hello world',
                'text_kor': '안녕하세요',
                'keywords': ['hello']
            }
        ],
        media_path="/path/to/video.mp4",
        template_name="template_1",
        output_dir=Path("output/batch_test")
    )
    
    job_id = await renderer.submit_job(job)
    
    # 작업 완료 대기
    while True:
        status = await renderer.get_job_status(job_id)
        if status and status.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            break
        await asyncio.sleep(1)
    
    # 통계 출력
    stats = renderer.get_statistics()
    print(f"Renderer statistics: {json.dumps(stats, indent=2)}")
    
    # 렌더러 중지
    await renderer.stop()


if __name__ == "__main__":
    asyncio.run(main())