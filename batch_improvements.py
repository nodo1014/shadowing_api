"""
Batch processing improvements for stability
배치 처리 안정성 개선
"""
import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path
import psutil
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchProcessManager:
    """배치 처리 최적화 관리자"""
    
    def __init__(self, max_concurrent: int = 3, max_memory_percent: int = 80):
        self.max_concurrent = max_concurrent
        self.max_memory_percent = max_memory_percent
        self.active_jobs = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    async def check_resources(self) -> bool:
        """리소스 사용 가능 여부 확인"""
        # 메모리 체크
        memory = psutil.virtual_memory()
        if memory.percent > self.max_memory_percent:
            logger.warning(f"Memory usage too high: {memory.percent}%")
            return False
            
        # 디스크 체크
        disk = shutil.disk_usage("/")
        free_gb = disk.free / (1024**3)
        if free_gb < 5:  # 최소 5GB 여유 공간
            logger.warning(f"Disk space too low: {free_gb:.1f}GB")
            return False
            
        return True
        
    async def process_clip_with_limit(self, clip_func, *args, **kwargs):
        """동시 실행 제한이 있는 클립 처리"""
        async with self.semaphore:
            # 리소스 체크
            if not await self.check_resources():
                # 리소스 부족시 대기
                await asyncio.sleep(5)
                
            # 처리 실행
            return await asyncio.get_event_loop().run_in_executor(
                None, clip_func, *args, **kwargs
            )
            
    def cleanup_temp_files(self, job_id: str):
        """임시 파일 정리"""
        try:
            # 특정 작업의 임시 파일 정리
            temp_patterns = [
                f"/tmp/*{job_id}*",
                f"/tmp/ffmpeg*",
                f"/tmp/tmp*"
            ]
            
            import glob
            for pattern in temp_patterns:
                for file in glob.glob(pattern):
                    try:
                        if Path(file).is_file():
                            Path(file).unlink()
                        elif Path(file).is_dir():
                            shutil.rmtree(file)
                    except Exception as e:
                        logger.debug(f"Failed to remove temp file {file}: {e}")
                        
        except Exception as e:
            logger.error(f"Temp file cleanup error: {e}")

# 개선된 배치 처리 함수
async def process_batch_clipping_improved(job_id: str, request, job_status: Dict, 
                                        output_dir: Path, template_encoder):
    """개선된 배치 클리핑 처리"""
    batch_manager = BatchProcessManager(max_concurrent=3)
    
    try:
        # 미디어 경로 검증
        from clipping_api import MediaValidator
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
            
        # 출력 디렉토리 생성
        job_dir = output_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        output_files = []
        failed_clips = []
        
        # 클립별 처리 함수
        def process_single_clip(idx: int, clip_data):
            """단일 클립 처리"""
            clip_num = idx + 1
            
            try:
                # 클립별 디렉토리
                clip_dir = job_dir / f"clip_{clip_num:03d}"
                clip_dir.mkdir(exist_ok=True)
                
                # 텍스트 블랭크 처리
                text_eng_blank = None
                if request.template_number in [2, 3]:
                    from clipping_api import generate_blank_text
                    text_eng_blank = generate_blank_text(clip_data.text_eng, clip_data.keywords)
                
                # 자막 데이터
                subtitle_data = {
                    'start_time': 0,
                    'end_time': clip_data.end_time - clip_data.start_time,
                    'english': clip_data.text_eng,
                    'korean': clip_data.text_kor,
                    'note': clip_data.note,
                    'eng': clip_data.text_eng,
                    'kor': clip_data.text_kor,
                    'keywords': clip_data.keywords,
                    'template_number': request.template_number,
                    'text_eng_blank': text_eng_blank
                }
                
                # 출력 경로
                output_path = clip_dir / f"clip_{clip_num:03d}.mp4"
                template_name = f"template_{request.template_number}"
                
                # 타임아웃 계산 (동적)
                clip_duration = clip_data.end_time - clip_data.start_time
                timeout = max(300, int(clip_duration * 10))  # 최소 5분, 클립 길이의 10배
                
                # 비디오 생성
                success = template_encoder.create_from_template(
                    template_name=template_name,
                    media_path=str(media_path),
                    subtitle_data=subtitle_data,
                    output_path=str(output_path),
                    start_time=clip_data.start_time,
                    end_time=clip_data.end_time,
                    padding_before=0.5,
                    padding_after=0.5,
                    save_individual_clips=request.individual_clips
                )
                
                if success:
                    return {
                        "success": True,
                        "clip_num": clip_num,
                        "file": str(output_path),
                        "start_time": clip_data.start_time,
                        "end_time": clip_data.end_time,
                        "text_eng": clip_data.text_eng[:50] + "..."
                    }
                else:
                    return {
                        "success": False,
                        "clip_num": clip_num,
                        "error": "Video creation failed"
                    }
                    
            except Exception as e:
                logger.error(f"Error processing clip {clip_num}: {e}", exc_info=True)
                return {
                    "success": False,
                    "clip_num": clip_num,
                    "error": str(e)
                }
            finally:
                # 클립별 임시 파일 정리
                batch_manager.cleanup_temp_files(f"{job_id}_clip_{clip_num}")
        
        # 동시 처리를 위한 태스크 생성
        tasks = []
        for idx, clip_data in enumerate(request.clips):
            task = batch_manager.process_clip_with_limit(
                process_single_clip, idx, clip_data
            )
            tasks.append(task)
            
        # 진행 상황 업데이트를 위한 처리
        completed = 0
        for future in asyncio.as_completed(tasks):
            result = await future
            completed += 1
            
            # 진행률 업데이트
            progress = int((completed / len(request.clips)) * 90)
            job_status[job_id]["progress"] = progress
            job_status[job_id]["message"] = f"클립 {completed}/{len(request.clips)} 처리 완료"
            
            if result["success"]:
                output_files.append(result)
                job_status[job_id]["completed_clips"] = len(output_files)
            else:
                failed_clips.append(result["clip_num"])
                job_status[job_id]["failed_clips"] = failed_clips
                
        # 최종 상태 업데이트
        if output_files:
            # 메타데이터 저장
            metadata = {
                "job_id": job_id,
                "media_path": str(media_path),
                "template_number": request.template_number,
                "total_clips": len(request.clips),
                "successful_clips": len(output_files),
                "failed_clips": len(failed_clips),
                "clips": output_files,
                "created_at": datetime.now().isoformat()
            }
            
            metadata_path = job_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            job_status[job_id]["status"] = "completed" if not failed_clips else "partial"
            job_status[job_id]["progress"] = 100
            job_status[job_id]["message"] = f"배치 클리핑 완료! ({len(output_files)}/{len(request.clips)}개 성공)"
            job_status[job_id]["output_files"] = output_files
        else:
            job_status[job_id]["status"] = "failed"
            job_status[job_id]["message"] = "모든 클립 생성 실패"
            
    except Exception as e:
        logger.error(f"Batch processing error: {e}", exc_info=True)
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["message"] = f"배치 처리 오류: {str(e)}"
    finally:
        # 전체 작업 임시 파일 정리
        batch_manager.cleanup_temp_files(job_id)