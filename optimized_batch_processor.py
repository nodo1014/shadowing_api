"""
Optimized batch processor for video clipping
최적화된 배치 처리 프로세서
"""
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import tempfile
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from subtitle_pipeline import SubtitlePipeline, SubtitleType
from template_video_encoder import TemplateVideoEncoder

logger = logging.getLogger(__name__)


@dataclass
class BatchClipTask:
    """배치 클립 작업 데이터"""
    clip_data: Dict
    media_path: str
    template_number: int
    output_path: str
    clip_number: int
    total_clips: int


class OptimizedBatchProcessor:
    """최적화된 배치 처리 프로세서"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.template_encoder = TemplateVideoEncoder()
        self._subtitle_cache = {}  # 자막 캐시
        self._media_info_cache = {}  # 미디어 정보 캐시
        
    async def process_batch(self, media_path: str, clips: List[Dict], 
                          template_number: int, output_dir: Path,
                          individual_clips: bool = True) -> List[Dict]:
        """배치 클립 처리 - 비동기 최적화"""
        
        # 1. 사전 처리: 모든 자막 데이터 준비
        subtitle_pipelines = self._prepare_all_subtitles(clips)
        
        # 2. 미디어 정보 캐싱
        media_info = await self._get_media_info_async(media_path)
        
        # 3. 작업 큐 생성
        tasks = []
        for idx, clip_data in enumerate(clips):
            clip_num = idx + 1
            clip_dir = output_dir / f"clip_{clip_num:03d}"
            clip_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = clip_dir / f"clip_{clip_num:03d}.mp4"
            
            task = BatchClipTask(
                clip_data=clip_data,
                media_path=media_path,
                template_number=template_number,
                output_path=str(output_path),
                clip_number=clip_num,
                total_clips=len(clips)
            )
            tasks.append(task)
        
        # 4. 병렬 처리 실행
        results = await self._process_tasks_parallel(tasks, subtitle_pipelines, individual_clips)
        
        # 5. 결과 정리
        output_files = []
        for result in results:
            if result['success']:
                output_files.append(result)
        
        logger.info(f"Batch processing completed: {len(output_files)}/{len(clips)} successful")
        return output_files
    
    def _prepare_all_subtitles(self, clips: List[Dict]) -> Dict[int, SubtitlePipeline]:
        """모든 자막을 미리 준비 (캐싱 활용)"""
        pipelines = {}
        
        for idx, clip_data in enumerate(clips):
            # 캐시 키 생성
            cache_key = self._create_subtitle_cache_key(clip_data)
            
            # 캐시 확인
            if cache_key in self._subtitle_cache:
                pipelines[idx] = self._subtitle_cache[cache_key]
                logger.debug(f"Using cached subtitle pipeline for clip {idx+1}")
            else:
                # 새로운 파이프라인 생성
                subtitle_data = {
                    'english': clip_data.get('text_eng', ''),
                    'korean': clip_data.get('text_kor', ''),
                    'note': clip_data.get('note', ''),
                    'keywords': clip_data.get('keywords', []),
                    'start_time': clip_data.get('start_time', 0),
                    'end_time': clip_data.get('end_time', 0)
                }
                
                pipeline = SubtitlePipeline(subtitle_data)
                # 모든 변형 미리 생성 (캐싱)
                pipeline.get_all_variants()
                
                pipelines[idx] = pipeline
                self._subtitle_cache[cache_key] = pipeline
                
        logger.info(f"Prepared {len(pipelines)} subtitle pipelines")
        return pipelines
    
    def _create_subtitle_cache_key(self, clip_data: Dict) -> str:
        """자막 캐시 키 생성"""
        # 텍스트와 키워드 기반 키 생성
        text_eng = clip_data.get('text_eng', '')
        text_kor = clip_data.get('text_kor', '')
        keywords = ','.join(sorted(clip_data.get('keywords', [])))
        return f"{text_eng}|{text_kor}|{keywords}"
    
    async def _get_media_info_async(self, media_path: str) -> Dict:
        """미디어 정보 비동기 가져오기"""
        if media_path in self._media_info_cache:
            return self._media_info_cache[media_path]
        
        # FFprobe를 사용하여 미디어 정보 가져오기
        import subprocess
        import json
        
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', media_path
        ]
        
        # 비동기 실행
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            info = json.loads(stdout)
            self._media_info_cache[media_path] = info
            return info
        else:
            logger.warning(f"Failed to get media info: {stderr.decode()}")
            return {}
    
    async def _process_tasks_parallel(self, tasks: List[BatchClipTask], 
                                    subtitle_pipelines: Dict[int, SubtitlePipeline],
                                    individual_clips: bool) -> List[Dict]:
        """작업을 병렬로 처리"""
        
        # 스레드풀 사용 (I/O 바운드 작업)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 비동기 작업 생성
            async_tasks = []
            
            for idx, task in enumerate(tasks):
                pipeline = subtitle_pipelines.get(idx)
                async_task = asyncio.create_task(
                    self._process_single_clip_async(task, pipeline, executor, individual_clips)
                )
                async_tasks.append(async_task)
            
            # 모든 작업 완료 대기
            results = await asyncio.gather(*async_tasks, return_exceptions=True)
            
            # 결과 처리
            processed_results = []
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Clip {idx+1} failed: {result}")
                    processed_results.append({
                        'success': False,
                        'clip_num': idx + 1,
                        'error': str(result)
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
    
    async def _process_single_clip_async(self, task: BatchClipTask, 
                                       pipeline: SubtitlePipeline,
                                       executor: ThreadPoolExecutor,
                                       individual_clips: bool) -> Dict:
        """단일 클립 비동기 처리"""
        
        try:
            # 진행 상태 로깅
            logger.info(f"Processing clip {task.clip_number}/{task.total_clips}")
            
            # 자막 파일 준비 (메모리에서)
            clip_duration = task.clip_data['end_time'] - task.clip_data['start_time']
            
            # 템플릿별 필요한 자막 타입 결정
            subtitle_files = await self._prepare_subtitle_files_async(
                pipeline, task.template_number, clip_duration
            )
            
            # FFmpeg 인코딩 (블로킹 작업이므로 스레드풀에서 실행)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                executor,
                self._encode_clip_sync,
                task, subtitle_files, individual_clips
            )
            
            # 임시 파일 정리
            for file_path in subtitle_files.values():
                if os.path.exists(file_path):
                    os.unlink(file_path)
            
            if success:
                return {
                    'success': True,
                    'clip_num': task.clip_number,
                    'file': str(task.output_path),
                    'start_time': task.clip_data['start_time'],
                    'end_time': task.clip_data['end_time']
                }
            else:
                return {
                    'success': False,
                    'clip_num': task.clip_number,
                    'error': 'Encoding failed'
                }
                
        except Exception as e:
            logger.error(f"Error processing clip {task.clip_number}: {e}")
            return {
                'success': False,
                'clip_num': task.clip_number,
                'error': str(e)
            }
    
    async def _prepare_subtitle_files_async(self, pipeline: SubtitlePipeline,
                                          template_number: int,
                                          clip_duration: float) -> Dict[str, str]:
        """자막 파일을 비동기로 준비"""
        subtitle_files = {}
        
        # 템플릿별 필요한 자막 타입
        template_subtitle_mapping = {
            1: [('full', SubtitleType.FULL)],
            2: [('blank_korean', SubtitleType.BLANK_KOREAN), 
                ('full', SubtitleType.FULL)],
            3: [('english', SubtitleType.ENGLISH_ONLY),
                ('korean', SubtitleType.KOREAN_ONLY),
                ('full', SubtitleType.FULL)]
        }
        
        needed_types = template_subtitle_mapping.get(template_number, [])
        
        for subtitle_key, variant_type in needed_types:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix=f'_{subtitle_key}.ass', delete=False) as tmp:
                # 자막 콘텐츠 가져오기 (캐시된 데이터 사용)
                content = pipeline.generate_ass_content(variant_type, clip_duration)
                tmp.write(content.encode('utf-8'))
                subtitle_files[subtitle_key] = tmp.name
        
        return subtitle_files
    
    def _encode_clip_sync(self, task: BatchClipTask, subtitle_files: Dict[str, str],
                         individual_clips: bool) -> bool:
        """동기 방식으로 클립 인코딩 (스레드풀에서 실행)"""
        try:
            # 템플릿 인코더 사용
            template_name = f"template_{task.template_number}"
            
            # 자막 데이터 준비
            subtitle_data = {
                'english': task.clip_data.get('text_eng', ''),
                'korean': task.clip_data.get('text_kor', ''),
                'note': task.clip_data.get('note', ''),
                'eng': task.clip_data.get('text_eng', ''),
                'kor': task.clip_data.get('text_kor', ''),
                'keywords': task.clip_data.get('keywords', []),
                'template_number': task.template_number
            }
            
            # 템플릿 인코더로 비디오 생성
            success = self.template_encoder.create_from_template(
                template_name=template_name,
                media_path=task.media_path,
                subtitle_data=subtitle_data,
                output_path=task.output_path,
                start_time=task.clip_data['start_time'],
                end_time=task.clip_data['end_time'],
                padding_before=0.5,
                padding_after=0.5,
                save_individual_clips=individual_clips
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return False


# 사용 예시
async def main():
    # 배치 프로세서 생성
    processor = OptimizedBatchProcessor(max_workers=4)
    
    # 테스트 클립 데이터
    clips = [
        {
            'start_time': 10.0,
            'end_time': 15.0,
            'text_eng': 'Hello, how are you?',
            'text_kor': '안녕하세요, 어떻게 지내세요?',
            'keywords': ['Hello', 'how']
        },
        {
            'start_time': 20.0,
            'end_time': 25.0,
            'text_eng': 'Nice to meet you.',
            'text_kor': '만나서 반갑습니다.',
            'keywords': ['Nice', 'meet']
        }
    ]
    
    # 배치 처리 실행
    output_dir = Path('output/batch_test')
    results = await processor.process_batch(
        media_path='/path/to/video.mp4',
        clips=clips,
        template_number=2,
        output_dir=output_dir,
        individual_clips=True
    )
    
    print(f"Processed {len(results)} clips successfully")


if __name__ == "__main__":
    asyncio.run(main())