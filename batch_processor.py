"""
Batch processing optimization for parallel video generation
병렬 비디오 생성을 위한 배치 처리 최적화
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import multiprocessing as mp

logger = logging.getLogger(__name__)

class BatchProcessor:
    """배치 작업 처리 클래스"""
    
    def __init__(self, max_workers: int = None, use_processes: bool = False):
        """
        Args:
            max_workers: 최대 워커 수 (None이면 CPU 코어 수 사용)
            use_processes: 프로세스 풀 사용 여부 (기본: 스레드 풀)
        """
        self.max_workers = max_workers or mp.cpu_count()
        self.use_processes = use_processes
        self.executor = None
        self._running = False
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        
    def start(self):
        """배치 프로세서 시작"""
        if self.use_processes:
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._running = True
        logger.info(f"BatchProcessor started with {self.max_workers} workers "
                   f"({'processes' if self.use_processes else 'threads'})")
        
    def stop(self):
        """배치 프로세서 정지"""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        self._running = False
        logger.info("BatchProcessor stopped")
        
    def process_batch(self, items: List[Any], process_func: Callable,
                     chunk_size: Optional[int] = None,
                     progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        배치 아이템 처리
        
        Args:
            items: 처리할 아이템 리스트
            process_func: 각 아이템을 처리할 함수
            chunk_size: 청크 크기 (None이면 워커당 균등 분배)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            처리 결과 리스트
        """
        if not self._running:
            raise RuntimeError("BatchProcessor not started")
            
        results = []
        total_items = len(items)
        completed = 0
        
        # 청크 크기 결정
        if chunk_size is None:
            chunk_size = max(1, total_items // (self.max_workers * 2))
            
        # 아이템을 청크로 분할
        chunks = [items[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
        
        logger.info(f"Processing {total_items} items in {len(chunks)} chunks")
        
        # 작업 제출
        future_to_chunk = {}
        for i, chunk in enumerate(chunks):
            future = self.executor.submit(self._process_chunk, chunk, process_func, i)
            future_to_chunk[future] = chunk
            
        # 결과 수집
        for future in as_completed(future_to_chunk):
            try:
                chunk_results = future.result()
                results.extend(chunk_results)
                completed += len(future_to_chunk[future])
                
                # 진행상황 콜백
                if progress_callback:
                    progress_callback(completed, total_items)
                    
                logger.debug(f"Completed {completed}/{total_items} items")
                
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                # 실패한 청크의 아이템들을 에러로 표시
                chunk = future_to_chunk[future]
                for item in chunk:
                    results.append({
                        "item": item,
                        "success": False,
                        "error": str(e)
                    })
                    
        return results
        
    def _process_chunk(self, chunk: List[Any], process_func: Callable, 
                      chunk_id: int) -> List[Dict[str, Any]]:
        """청크 처리 (워커에서 실행)"""
        results = []
        
        for item in chunk:
            try:
                start_time = datetime.utcnow()
                result = process_func(item)
                end_time = datetime.utcnow()
                
                results.append({
                    "item": item,
                    "success": True,
                    "result": result,
                    "processing_time": (end_time - start_time).total_seconds()
                })
                
            except Exception as e:
                logger.error(f"Error processing item in chunk {chunk_id}: {e}")
                results.append({
                    "item": item,
                    "success": False,
                    "error": str(e),
                    "processing_time": 0
                })
                
        return results
        
    async def process_batch_async(self, items: List[Any], process_func: Callable,
                                 max_concurrent: int = 10,
                                 progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        비동기 배치 처리
        
        Args:
            items: 처리할 아이템 리스트
            process_func: 각 아이템을 처리할 비동기 함수
            max_concurrent: 최대 동시 실행 수
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            처리 결과 리스트
        """
        results = []
        total_items = len(items)
        completed = 0
        
        # 세마포어로 동시 실행 제한
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(item, index):
            async with semaphore:
                try:
                    start_time = datetime.utcnow()
                    result = await process_func(item)
                    end_time = datetime.utcnow()
                    
                    return {
                        "item": item,
                        "index": index,
                        "success": True,
                        "result": result,
                        "processing_time": (end_time - start_time).total_seconds()
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing item {index}: {e}")
                    return {
                        "item": item,
                        "index": index,
                        "success": False,
                        "error": str(e),
                        "processing_time": 0
                    }
                    
        # 모든 작업 생성
        tasks = [process_with_semaphore(item, i) for i, item in enumerate(items)]
        
        # 작업 실행 및 결과 수집
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            # 진행상황 콜백
            if progress_callback:
                await progress_callback(completed, total_items)
                
            logger.debug(f"Completed {completed}/{total_items} items")
            
        # 원래 순서대로 정렬
        results.sort(key=lambda x: x["index"])
        
        return results


# 사용 예시 함수들
def create_batch_video_processor(template_encoder):
    """비디오 생성용 배치 프로세서 생성"""
    
    def process_video_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """개별 비디오 아이템 처리"""
        try:
            success = template_encoder.create_from_template(
                template_name=item["template_name"],
                media_path=item["media_path"],
                subtitle_data=item["subtitle_data"],
                output_path=item["output_path"],
                start_time=item.get("start_time"),
                end_time=item.get("end_time"),
                save_individual_clips=item.get("save_individual_clips", True)
            )
            
            return {
                "success": success,
                "output_path": item["output_path"] if success else None
            }
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    return process_video_item