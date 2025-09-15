"""
Template-based video encoder
템플릿 기반으로 shadowing 비디오를 생성하는 개선된 인코더
"""
import json
import os
import tempfile
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from video_encoder import VideoEncoder
from subtitle_generator import SubtitleGenerator
from subtitle_pipeline import SubtitlePipeline, SubtitleType
from img_tts_generator import ImgTTSGenerator
from template_standards import TemplateStandards

# OpenCV for face detection (optional)
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("OpenCV not available, 'face' aspect ratio option will fallback to 'center'")

# Import database utilities for logging
try:
    from database_v2.models_v2 import DatabaseManager
    from api.db_utils import add_processing_log, create_output_video
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)
if not DB_AVAILABLE:
    logger.warning("Database modules not available, processing logs will not be saved to DB")


class TemplateVideoEncoder(VideoEncoder):
    """템플릿 기반 비디오 인코더"""
    
    def __init__(self):
        super().__init__()
        self.subtitle_generator = SubtitleGenerator()
        self.templates, self.subtitle_mode_labels = self._load_templates()
    
    def _load_templates(self) -> tuple:
        """템플릿 파일 로드"""
        template_path = Path(__file__).parent / "templates" / "shadowing_patterns.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                patterns = data.get('patterns', {})
                subtitle_mode_labels = data.get('subtitle_mode_labels', {})
                return patterns, subtitle_mode_labels
        return {}, {}
    
    def create_from_template(self, template_name: str, media_path: str, 
                           subtitle_data: Dict, output_path: str,
                           start_time: float = None, end_time: float = None,
                           padding_before: float = 0.5, padding_after: float = 0.5,
                           save_individual_clips: bool = True) -> bool:
        """템플릿을 사용하여 shadowing 비디오 생성"""
        
        if template_name not in self.templates:
            logger.error(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        logger.info(f"Using template: {template['name']} - {template['description']}")
        
        # Extract job_id from output path if available
        job_id = None
        if output_path:
            output_parts = Path(output_path).parts
            # 일반적으로: /output/YYYY-MM-DD/job_id/filename.mp4
            if len(output_parts) >= 3:
                potential_job_id = output_parts[-2]
                # UUID 형식 검증
                try:
                    import uuid
                    uuid.UUID(potential_job_id)
                    job_id = potential_job_id
                    self._current_job_id = job_id  # Store for individual clips
                except ValueError:
                    pass
        
        # Log to DB if available
        if DB_AVAILABLE and job_id:
            try:
                with DatabaseManager.get_session() as session:
                    add_processing_log(
                        session=session,
                        job_id=job_id,
                        level="info",
                        stage="template_encoding",
                        message=f"Starting template encoding with {template_name}",
                        details={"template": template_name, "media": media_path}
                    )
            except Exception as e:
                logger.warning(f"Failed to log to DB: {e}")
        
        # 현재 템플릿 이름 저장 (쇼츠 여부 확인용)
        self._current_template_name = template_name
        
        # subtitle_data 저장 (keep_aspect_ratio 등 옵션 접근용)
        self._current_subtitle_data = subtitle_data
        
        # 타이틀 정보 저장 (쇼츠용)
        self._title_line1 = subtitle_data.get('title_1', '')
        self._title_line2 = subtitle_data.get('title_2', '')
        self._title_line3 = subtitle_data.get('title_3', '')
        
        # Calculate padded times
        if start_time is not None and end_time is not None:
            padded_start = max(0, start_time - padding_before)
            padded_end = end_time + padding_after
            duration = padded_end - padded_start
        else:
            padded_start = None
            duration = None
        
        # Get gap duration from template
        gap_duration = template.get('gap_duration', 1.5)
        
        # Prepare subtitle files with gap duration
        subtitle_files = self._prepare_subtitle_files(subtitle_data, template_name, duration, gap_duration)
        
        # Create clips based on template
        temp_clips = []
        clip_base_dir = None
        
        if save_individual_clips:
            clip_base_dir = Path(output_path).parent / "individual_clips"
            clip_base_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            clip_number = Path(output_path).stem.split('_')[-1] if '_' in Path(output_path).stem else '0000'
            
            # 전체 클립 수 계산
            total_clips = sum(clip['count'] for clip in template['clips'])
            current_clip_index = 0
            
            for clip_config in template['clips']:
                for i in range(clip_config['count']):
                    current_clip_index += 1
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_clips.append(temp_file.name)
                    temp_file.close()
                    
                    # Get subtitle file for this clip
                    subtitle_file = subtitle_files.get(clip_config['subtitle_type'])
                    logger.info(f"Template {template_name}, clip {i+1}: subtitle_type={clip_config['subtitle_type']}, subtitle_file={subtitle_file}")
                    if subtitle_file and not os.path.exists(subtitle_file):
                        logger.error(f"Subtitle file does not exist: {subtitle_file}")
                    
                    # Store progress info for encoding
                    self._current_clip_index = current_clip_index
                    self._total_clips = total_clips
                    
                    # Check if this clip should use still frame mode
                    video_mode = clip_config.get('video_mode', 'normal')
                    
                    # Check for pre_silence
                    pre_silence = clip_config.get('pre_silence', 0.0)
                    post_silence = clip_config.get('post_silence', 0.0)
                    
                    # Create temporary clip without pre_silence first
                    temp_clip_no_silence = None
                    if pre_silence > 0:
                        temp_clip_no_silence = tempfile.NamedTemporaryFile(suffix='_no_silence.mp4', delete=False)
                        temp_clip_no_silence.close()
                        actual_output = temp_clip_no_silence.name
                    else:
                        actual_output = temp_clips[-1]
                    
                    # Encode the clip based on video mode
                    if video_mode == 'still_frame':
                        if not self._encode_still_frame_clip(media_path, actual_output,
                                                           padded_start, duration,
                                                           subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create still frame {clip_config['subtitle_mode']} clip")
                    elif video_mode in ['still_frame_tts', 'still_frame_original', 'still_frame_kor_tts'] and clip_config.get('use_img_tts_generator'):
                        # Use img_tts_generator for study clips
                        if not self._encode_study_clip(media_path, actual_output,
                                                      padded_start, duration,
                                                      subtitle_data, clip_config):
                            raise Exception(f"Failed to create study {clip_config['subtitle_mode']} clip")
                    elif video_mode == 'slow_motion':
                        # Slow motion video with speed adjustment
                        speed = clip_config.get('speed', 0.7)
                        if not self._encode_slow_motion_clip(media_path, actual_output,
                                                           padded_start, duration,
                                                           subtitle_file=subtitle_file,
                                                           speed=speed):
                            raise Exception(f"Failed to create slow motion {clip_config['subtitle_mode']} clip")
                    else:
                        # Pass subtitle_mode to encoding method
                        self._current_subtitle_mode = clip_config.get('subtitle_mode')
                        if not self._encode_clip(media_path, actual_output,
                                               padded_start, duration,
                                               subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create {clip_config['subtitle_mode']} clip")
                    
                    # Add pre_silence if needed
                    if pre_silence > 0 and temp_clip_no_silence:
                        # 쫼츠 여부 확인
                        is_shorts = '_shorts' in self._current_template_name if hasattr(self, '_current_template_name') else False
                        resolution = (1080, 1920) if is_shorts else (1920, 1080)
                        
                        # Create black video for pre_silence and concatenate
                        cmd = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi',
                            '-i', f'color=black:s={resolution[0]}x{resolution[1]}:d={pre_silence}',
                            '-f', 'lavfi', 
                            '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={pre_silence}',
                            '-i', temp_clip_no_silence.name,
                            '-filter_complex',
                            '[0:v][2:v]concat=n=2:v=1:a=0[outv];[1:a][2:a]concat=n=2:v=0:a=1[outa]',
                            '-map', '[outv]',
                            '-map', '[outa]',
                            '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
                            '-preset', TemplateStandards.STANDARD_VIDEO_PRESET,
                            '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
                            '-c:a', TemplateStandards.OUTPUT_AUDIO_CODEC,
                            '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
                            '-ar', str(TemplateStandards.OUTPUT_SAMPLE_RATE),
                            '-ac', str(TemplateStandards.OUTPUT_CHANNELS),
                            '-movflags', '+faststart',
                            temp_clips[-1]
                        ]
                        
                        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
                        if returncode != 0:
                            logger.error(f"Failed to add pre_silence: {stderr}")
                            raise Exception(f"Failed to add pre_silence to {clip_config['subtitle_mode']} clip")
                        
                        # Clean up temporary file
                        os.unlink(temp_clip_no_silence.name)
                    
                    # Save individual clip if requested
                    if save_individual_clips and clip_base_dir:
                        folder_name = clip_config.get('folder_name', clip_config['subtitle_mode'])
                        self._save_individual_clip(temp_clips[-1], clip_base_dir,
                                                 folder_name, i + 1, clip_number)
                    
                    logger.info(f"Created {clip_config['subtitle_mode']} clip {i+1}/{clip_config['count']}")
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Concatenate clips with gaps
            gap_duration = template.get('gap_duration', 1.5)
            logger.info(f"Using gap_duration from template '{template_name}': {gap_duration} seconds")
            if not self._concatenate_clips(temp_clips, output_path, gap_duration):
                raise Exception("Failed to concatenate clips")
            
            logger.info(f"Successfully created shadowing video: {output_path}")
            
            # Log successful completion to DB
            if DB_AVAILABLE and job_id:
                try:
                    with DatabaseManager.get_session() as session:
                        add_processing_log(
                            session=session,
                            job_id=job_id,
                            level="info",
                            stage="template_encoding_complete",
                            message=f"Successfully created video with {template_name}",
                            details={
                                "output": str(output_path),
                                "clips_count": len(temp_clips),
                                "duration": duration
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to log completion to DB: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating video from template: {e}", exc_info=True)
            
            # Log error to DB
            if DB_AVAILABLE and job_id:
                try:
                    with DatabaseManager.get_session() as session:
                        add_processing_log(
                            session=session,
                            job_id=job_id,
                            level="error",
                            stage="template_encoding_error",
                            message=f"Failed to create video with {template_name}",
                            details={"error": str(e)}
                        )
                except Exception as db_e:
                    logger.warning(f"Failed to log error to DB: {db_e}")
            
            return False
            
        finally:
            # Clean up
            for temp_clip in temp_clips:
                if os.path.exists(temp_clip):
                    os.unlink(temp_clip)
            
            # Clean up subtitle files (temporarily disabled for debugging)
            # for subtitle_file in subtitle_files.values():
            #     if subtitle_file and os.path.exists(subtitle_file):
            #         os.unlink(subtitle_file)
    
    def _prepare_subtitle_files(self, subtitle_data: Dict, template_name: str, clip_duration: float = None, gap_duration: float = 0.0) -> Dict[str, str]:
        """템플릿에 필요한 자막 파일들을 준비 - 새로운 파이프라인 사용"""
        subtitle_files = {}
        
        # 디버깅을 위한 로깅 추가
        logger.info(f"_prepare_subtitle_files called with template_name: {template_name}")
        logger.info(f"subtitle_data keys: {list(subtitle_data.keys())}")
        logger.info(f"template_number: {subtitle_data.get('template_number')}")
        logger.info(f"text_eng: {subtitle_data.get('text_eng', 'NOT FOUND')}")
        logger.info(f"text_kor: {subtitle_data.get('text_kor', 'NOT FOUND')}")
        
        # Template 0, 10 (원본 구간 추출)의 경우 이미 생성된 ASS 파일 사용 (있는 경우에만)
        if subtitle_data.get('template_number') in [0, 10] and 'ass_file' in subtitle_data:
            subtitle_files['full'] = subtitle_data['ass_file']
            logger.info(f"Using pre-generated ASS file for template {subtitle_data.get('template_number')}: {subtitle_data['ass_file']}")
            return subtitle_files
        
        # Template 10이지만 ass_file이 없는 경우 일반 자막 생성으로 진행
        if subtitle_data.get('template_number') == 10:
            logger.info("Template 10 without pre-generated ASS file, generating subtitle normally")
        
        # 템플릿에서 필요한 subtitle_type들을 추출
        template = self.templates.get(template_name)
        if not template:
            return subtitle_files
            
        needed_types = set()
        for clip in template['clips']:
            if clip['subtitle_type']:
                needed_types.add(clip['subtitle_type'])
        
        # Add timing information if not present
        if 'start_time' not in subtitle_data:
            subtitle_data['start_time'] = 0.0
        if 'end_time' not in subtitle_data:
            subtitle_data['end_time'] = clip_duration if clip_duration else 5.0
            
        # 효율적인 자막 파이프라인 사용
        # 쇼츠 템플릿인 경우 줄바꿈 설정 추가
        is_shorts = '_shorts' in template_name
        if is_shorts:
            subtitle_data['max_chars_per_line'] = 15  # 쇼츠용 짧은 줄
            subtitle_data['is_shorts'] = True
        pipeline = SubtitlePipeline(subtitle_data)
        
        # 디버깅: SubtitlePipeline 생성 후 확인
        logger.info(f"SubtitlePipeline created - english: {pipeline.english}, korean: {pipeline.korean}")
        
        # Map template subtitle types to pipeline types
        type_mapping = {
            'full': SubtitleType.FULL,
            'blank': SubtitleType.BLANK,
            'korean': SubtitleType.KOREAN_ONLY,
            'blank_korean': SubtitleType.BLANK_KOREAN,
        }
        
        # Gap duration을 포함한 총 클립 길이 계산
        total_clip_duration = clip_duration + gap_duration if clip_duration else None
        
        # 필요한 자막 파일들 생성 (파이프라인 사용)
        for subtitle_type in needed_types:
            if subtitle_type in type_mapping:
                variant_type = type_mapping[subtitle_type]
                
                # 임시 파일 생성
                temp_file = tempfile.NamedTemporaryFile(suffix=f'_{subtitle_type}.ass', delete=False)
                temp_file.close()
                
                # 파이프라인으로 자막 저장
                pipeline.save_variant_to_file(variant_type, temp_file.name, total_clip_duration)
                subtitle_files[subtitle_type] = temp_file.name
                
                # 디버깅: 생성된 자막 파일 내용 확인
                with open(temp_file.name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"Generated {subtitle_type} subtitle file: {temp_file.name}")
                    logger.info(f"File size: {len(content)} bytes")
                    logger.info(f"First 200 chars: {content[:200]}")
                
                logger.debug(f"Generated {subtitle_type} subtitle using pipeline")
        
        # 기존 방식으로 fallback (pipeline에서 지원하지 않는 타입)
        if len(subtitle_files) < len(needed_types):
            missing_types = needed_types - set(subtitle_files.keys())
            logger.warning(f"Pipeline doesn't support types: {missing_types}, using legacy generator")
            
            for subtitle_type in missing_types:
                # Legacy subtitle generation code here if needed
                pass
        
        return subtitle_files
    
    def _save_individual_clip(self, clip_path: str, base_dir: Path, 
                            clip_type: str, index: int, clip_number: str):
        """개별 클립 저장"""
        import shutil
        
        # subtitle_mode를 기반으로 디렉토리 이름 생성
        # 새로운 mode가 추가되어도 자동으로 처리됨
        sub_dir = base_dir / clip_type
        sub_dir.mkdir(exist_ok=True)
        
        dest_file = sub_dir / f"clip_{clip_number}_{index}.mp4"
        shutil.copy2(clip_path, str(dest_file))
        logger.debug(f"Saved: {dest_file.relative_to(base_dir)}")
        
        # Save to DB if available
        if DB_AVAILABLE and hasattr(self, '_current_job_id') and self._current_job_id:
            try:
                with DatabaseManager.get_session() as session:
                    # Determine effect and subtitle mode from clip type
                    effect_type = 'none'
                    subtitle_mode = clip_type
                    
                    if 'blur' in clip_type:
                        effect_type = 'blur'
                    elif 'crop' in clip_type:
                        effect_type = 'crop'
                    elif 'fit' in clip_type:
                        effect_type = 'fit'
                    
                    create_output_video(
                        session=session,
                        job_id=self._current_job_id,
                        video_type="individual_clip",
                        file_path=str(dest_file),
                        effect_type=effect_type,
                        subtitle_mode=subtitle_mode,
                        index=index
                    )
            except Exception as e:
                logger.warning(f"Failed to save individual clip to DB: {e}")
    
    def _concatenate_clips(self, clips: List[str], output_path: str, gap_duration: float = 1.5) -> bool:
        """프리즈 프레임 갭을 사용하여 클립들을 병합 - 현재 템플릿의 gap_duration 사용"""
        if not clips:
            logger.error("No clips to concatenate")
            return False
        
        # 단일 클립인 경우 그냥 복사
        if len(clips) == 1:
            import shutil
            shutil.copy2(clips[0], output_path)
            return True
        
        logger.info(f"Starting concatenation of {len(clips)} clips with {gap_duration}s gaps")
        
        # 각 클립의 마지막 프레임으로 프리즈 프레임 생성
        clips_with_gaps = []
        temp_gaps = []
        
        # 쇼츠 여부 확인
        is_shorts = '_shorts' in self._current_template_name if hasattr(self, '_current_template_name') else False
        
        for i, clip in enumerate(clips):
            clips_with_gaps.append(clip)
            
            # 마지막 클립이 아니면 갭 추가
            if i < len(clips) - 1 and gap_duration > 0:
                # 클립의 길이 구하기
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    clip
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                
                try:
                    clip_duration = float(result.stdout.strip())
                except ValueError:
                    logger.warning(f"Could not get duration for clip {i+1}, using default")
                    clip_duration = 5.0
                
                # 마지막 프레임 시간 (끝에서 0.1초 전)
                last_frame_time = max(0, clip_duration - 0.1)
                
                # 프리즈 프레임 생성
                temp_gap = tempfile.NamedTemporaryFile(suffix='_gap.mp4', delete=False)
                temp_gap.close()
                temp_gaps.append(temp_gap.name)
                
                # 쇼츠인 경우 해상도 설정
                if is_shorts:
                    freeze_frame = TemplateStandards.create_freeze_frame(
                        clip, last_frame_time, gap_duration, temp_gap.name
                    )
                    # 쇼츠 해상도로 변경
                    temp_gap_shorts = tempfile.NamedTemporaryFile(suffix='_gap_shorts.mp4', delete=False)
                    temp_gap_shorts.close()
                    
                    resize_cmd = [
                        'ffmpeg', '-y',
                        '-i', temp_gap.name,
                        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                        '-c:a', 'copy',
                        temp_gap_shorts.name
                    ]
                    
                    result = subprocess.run(resize_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        os.unlink(temp_gap.name)
                        temp_gaps[-1] = temp_gap_shorts.name
                        clips_with_gaps.append(temp_gap_shorts.name)
                    else:
                        logger.warning(f"Failed to resize gap for shorts: {result.stderr}")
                        clips_with_gaps.append(temp_gap.name)
                else:
                    freeze_frame = TemplateStandards.create_freeze_frame(
                        clip, last_frame_time, gap_duration, temp_gap.name
                    )
                    clips_with_gaps.append(freeze_frame)
                
                logger.info(f"Created {gap_duration}s gap after clip {i+1}")
        
        # 병합 수행
        result = TemplateStandards.merge_clips(clips_with_gaps, output_path, mode='reencode')
        
        # 임시 갭 파일들 정리
        for temp_gap in temp_gaps:
            if os.path.exists(temp_gap):
                os.unlink(temp_gap)
        
        return result
    
    def _encode_still_frame_clip(self, media_path: str, output_path: str,
                               start_time: float = None, duration: float = None,
                               subtitle_file: str = None) -> bool:
        """정지 프레임 클립 생성 (중간 프레임 사용)"""
        
        if start_time is None or duration is None:
            logger.error("start_time and duration are required for still frame clips")
            return False
        
        # 구간의 중간 시점 계산
        middle_time = start_time + (duration / 2)
        
        try:
            # ImgTTSGenerator 사용하여 정지 프레임 생성
            generator = ImgTTSGenerator()
            
            # 오디오는 원본 사용, 비디오는 정지 프레임
            success = generator.create_still_frame_video(
                media_path=media_path,
                output_path=output_path,
                frame_time=middle_time,
                start_time=start_time,
                duration=duration,
                subtitle_file=subtitle_file,
                use_original_audio=True
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating still frame clip: {e}", exc_info=True)
            return False
    
    def _encode_clip(self, input_path: str, output_path: str,
                    start_time: float = None, duration: float = None,
                    subtitle_file: str = None) -> bool:
        """비디오 클립 인코딩 - 쇼츠 템플릿일 경우 크롭 적용"""
        
        # 현재 템플릿이 쇼츠인지 확인
        current_template = getattr(self, '_current_template_name', '')
        is_shorts = '_shorts' in current_template
        
        # 쇼츠 여부를 부모 클래스에 전달
        if is_shorts:
            self._is_shorts_encoding = True
        
        if is_shorts:
            # 쇼츠용 크롭 적용
            return self._encode_clip_with_crop(input_path, output_path, 
                                             start_time, duration, 
                                             subtitle_file, 
                                             width=1080, height=1920)
        else:
            # 일반 인코딩 (타이틀 필터 적용을 위해 오버라이드)
            return self._encode_clip_with_title(input_path, output_path, 
                                               start_time, duration, 
                                               subtitle_file)
    
    def _encode_clip_with_crop(self, input_path: str, output_path: str,
                             start_time: float = None, duration: float = None,
                             subtitle_file: str = None, 
                             width: int = 1080, height: int = 1920) -> bool:
        """크롭을 적용한 클립 인코딩 (쇼츠용)"""
        
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # 템플릿 이름에 따라 다른 크롭 방식 적용
        current_template = getattr(self, '_current_template_name', '')
        
        # aspect_ratio 옵션 확인 (템플릿 10용)
        aspect_ratio = 'center'  # 기본값
        if hasattr(self, '_current_subtitle_data') and self._current_subtitle_data:
            aspect_ratio = self._current_subtitle_data.get('aspect_ratio', 'center')
        
        if 'template_original_shorts' in current_template:
            if aspect_ratio == 'origin':
                # 원본 비율 유지: 축소하여 중앙 배치
                video_filter = f"scale='if(gt(iw/ih,{width}/{height}),{width},-1)':'if(gt(iw/ih,{width}/{height}),-1,{height})',pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
            elif aspect_ratio == 'top':
                # 상단 기준 크롭: 인물 얼굴이 상단에 있을 때
                video_filter = f"crop='ih*9/16:ih:(iw-ih*9/16)/2:0',scale={width}:{height}"
            elif aspect_ratio == 'bottom':
                # 하단 기준 크롭: 하단 자막이나 액션이 중요할 때
                video_filter = f"crop='ih*9/16:ih:(iw-ih*9/16)/2:ih-ih',scale={width}:{height}"
            elif aspect_ratio == 'zoom':
                # 중앙 80% 확대: 클로즈업 효과
                video_filter = f"crop='iw*0.8:ih*0.8',scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
            elif aspect_ratio == 'wide':
                # 와이드 크롭: 좌우 10%만 자르고 상하 여백
                video_filter = f"crop='iw*0.8:ih:iw*0.1:0',scale={width}:-1,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
            elif aspect_ratio == 'face' and CV2_AVAILABLE:
                # 얼굴 인식 기반 크롭
                face_crop = self._get_face_crop_params(input_path, start_time)
                if face_crop:
                    x, y, w, h = face_crop
                    # 얼굴 영역을 중심으로 9:16 비율로 크롭
                    video_filter = f"crop={w}:{h}:{x}:{y},scale={width}:{height}"
                else:
                    # 얼굴을 찾지 못하면 center로 fallback
                    video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
            else:  # 'center' 또는 기본값
                # 중앙 정사각형 크롭
                video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        elif 'template_1_shorts' in current_template:
            # 쇼츠 1: 원본 100% 정사각형 크롭
            video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        elif 'template_2_shorts' in current_template:
            # 쇼츠 2: 좌우 15%씩 크롭, 원본 높이 유지
            video_filter = f"crop='iw*0.7:ih:iw*0.15:0',scale='if(gt(iw,1080),1080,iw)':'if(gt(iw,1080),ih*1080/iw,ih)',pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        elif 'template_3_shorts' in current_template:
            # 쇼츠 3: 원본 크기 그대로 축소하여 전체 화면 보이기
            video_filter = f"scale='if(gt(iw/ih,{width}/{height}),{width},-1)':'if(gt(iw/ih,{width}/{height}),-1,{height})',pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        else:
            # 기본값: 원본 100% 정사각형 크롭
            video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        
        if subtitle_file and os.path.exists(subtitle_file):
            # FFmpeg ass 필터를 위한 올바른 이스케이핑
            abs_path = os.path.abspath(subtitle_file)
            # Windows 호환을 위해 백슬래시를 슬래시로 변환
            subtitle_path = abs_path.replace('\\', '/')
            # FFmpeg ass 필터를 위한 특수 문자 이스케이핑
            subtitle_path = subtitle_path.replace(':', '\\:').replace('[', '\\[').replace(']', '\\]')
            subtitle_path = subtitle_path.replace(',', '\\,').replace("'", "\\'").replace(' ', '\\ ')
            video_filter += f",ass={subtitle_path}"
            logger.info(f"Adding ASS subtitle filter for shorts: ass={subtitle_path}")
            
            # 디버깅: ASS 파일 내용 확인
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"ASS file content length: {len(content)} bytes")
                if 'Dialogue:' in content:
                    dialogue_lines = [line for line in content.split('\n') if line.startswith('Dialogue:')]
                    logger.info(f"Found {len(dialogue_lines)} dialogue lines in ASS file")
                    if dialogue_lines:
                        logger.info(f"First dialogue: {dialogue_lines[0]}")
                else:
                    logger.warning("No 'Dialogue:' lines found in ASS file!")
        else:
            logger.warning(f"Subtitle file not found or not provided: {subtitle_file}")
        
        # 템플릿에 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            video_filter += f",{title_filter}"
        
        cmd.extend(['-vf', video_filter])
        
        # 인코딩 설정 (일반 인코딩과 동일하게 통일)
        cmd.extend([
            '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
            '-preset', TemplateStandards.STANDARD_VIDEO_PRESET,
            '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
            '-profile:v', TemplateStandards.STANDARD_VIDEO_PROFILE,
            '-level', TemplateStandards.STANDARD_VIDEO_LEVEL,
            '-pix_fmt', TemplateStandards.STANDARD_PIX_FMT,
            '-r', str(TemplateStandards.STANDARD_FRAMERATE),
            '-c:a', TemplateStandards.OUTPUT_AUDIO_CODEC,
            '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
            '-ar', str(TemplateStandards.OUTPUT_SAMPLE_RATE),
            '-ac', str(TemplateStandards.OUTPUT_CHANNELS),
            '-movflags', '+faststart',
            output_path
        ])
        
        logger.info(f"Encoding clip with command: {' '.join(cmd[:10])}...")
        
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _encode_study_clip(self, media_path: str, output_path: str,
                         start_time: float = None, duration: float = None,
                         subtitle_data: Dict = None, clip_config: Dict = None) -> bool:
        """스터디 클립 생성 (ImgTTSGenerator 사용)"""
        try:
            generator = ImgTTSGenerator()
            
            # 쇼츠 여부 확인
            is_shorts = 'shorts' in clip_config.get('subtitle_mode', '')
            
            # 비디오 모드 확인
            video_mode = clip_config.get('video_mode', 'still_frame_tts')
            use_original_audio = clip_config.get('use_original_audio', False) or (video_mode == 'still_frame_original')
            
            # 스터디 모드에 따른 설정
            if 'preview' in clip_config.get('subtitle_mode', ''):
                # 미리보기: 시작 부분 프레임
                frame_time = start_time + 0.5 if start_time else 0.5
            elif 'review' in clip_config.get('subtitle_mode', ''):
                # 복습: 중간 부분 프레임
                frame_time = start_time + (duration / 2) if start_time and duration else 2.5
            else:
                # 기본: 중간 프레임
                frame_time = start_time + (duration / 2) if start_time and duration else 2.5
            
            # TTS 언어 설정
            tts_language = 'english'  # 기본값
            if video_mode == 'still_frame_kor_tts':
                tts_language = 'korean'
            
            # 스터디 클립 생성
            success = generator.create_study_clip(
                media_path=media_path,
                output_path=output_path,
                frame_time=frame_time,
                start_time=start_time,
                end_time=start_time + duration if start_time and duration else None,
                text_eng=subtitle_data.get('text_eng', ''),
                text_kor=subtitle_data.get('text_kor', ''),
                use_original_audio=use_original_audio,
                is_shorts=is_shorts,
                tts_language=tts_language
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating study clip: {e}", exc_info=True)
            return False
    
    def _get_title_filter(self) -> str:
        """타이틀 필터 생성 (쇼츠와 일반 템플릿 구분)"""
        current_template = getattr(self, '_current_template_name', '')
        is_shorts = '_shorts' in current_template
        
        if is_shorts:
            return self._get_shorts_title_filter()
        else:
            return self._get_general_title_filter()
    
    def _get_shorts_title_filter(self) -> str:
        """쇼츠용 타이틀 필터"""
        filters = []
        
        # 폰트 파일 경로
        font_file = "/home/kang/.fonts/TmonMonsori.ttf"
        if not os.path.exists(font_file):
            font_file = "NanumGothic"  # 폴백 폰트
        
        current_template = getattr(self, '_current_template_name', '')
        
        # 템플릿별 타이틀 처리
        if 'template_1_shorts' in current_template:
            # 쇼츠 1: 상단 2줄 타이틀
            if self._title_line1:
                filters.append(
                    f"drawtext=text='{self._title_line1}':"
                    f"fontfile={font_file}:fontsize=120:"
                    f"fontcolor=white:borderw=5:bordercolor=black:"
                    f"x=(w-text_w)/2:y=200"
                )
            if self._title_line2:
                filters.append(
                    f"drawtext=text='{self._title_line2}':"
                    f"fontfile={font_file}:fontsize=90:"
                    f"fontcolor=#FFD700:borderw=4:bordercolor=black:"
                    f"x=(w-text_w)/2:y=350"
                )
        
        elif 'template_2_shorts' in current_template or 'template_3_shorts' in current_template:
            # 쇼츠 2, 3: 상단 타이틀
            if self._title_line1:
                filters.append(
                    f"drawtext=text='{self._title_line1}':"
                    f"fontfile={font_file}:fontsize=100:"
                    f"fontcolor=white:borderw=5:bordercolor=black:"
                    f"x=(w-text_w)/2:y=150"
                )
            if self._title_line2:
                filters.append(
                    f"drawtext=text='{self._title_line2}':"
                    f"fontfile={font_file}:fontsize=80:"
                    f"fontcolor=#FFD700:borderw=4:bordercolor=black:"
                    f"x=(w-text_w)/2:y=280"
                )
            
            # 타이틀 3 (멀티라인 지원)
            if hasattr(self, '_title_line3') and self._title_line3:
                lines = self._title_line3.split('\\n')
                y_offset = 420
                for line in lines:
                    filters.append(
                        f"drawtext=text='{line}':"
                        f"fontfile={font_file}:fontsize=60:"
                        f"fontcolor=white:borderw=3:bordercolor=black:"
                        f"x=(w-text_w)/2:y={y_offset}"
                    )
                    y_offset += 80
        
        return ",".join(filters)
    
    def _get_general_title_filter(self) -> str:
        """일반 템플릿용 타이틀 필터"""
        filters = []
        
        # 폰트 파일 경로
        font_file = "/home/kang/.fonts/TmonMonsori.ttf"
        if not os.path.exists(font_file):
            font_file = "NanumGothic"  # 폴백 폰트
        
        # 타이틀 라인 1 (왼쪽 상단)
        if self._title_line1:
            filters.append(
                f"drawtext=text='{self._title_line1}':"
                f"fontfile={font_file}:fontsize=40:"
                f"fontcolor=white:borderw=3:bordercolor=black:"
                f"x=80:y=150"
            )
        
        # 타이틀 라인 2 (오른쪽 상단)
        if self._title_line2:
            # 텍스트 너비를 고려한 오른쪽 정렬
            y_offset = 150 if self._title_line1 else 200
            filters.append(
                f"drawtext=text='{self._title_line2}':"
                f"fontfile={font_file}:fontsize=40:"
                f"fontcolor=#C0C0C0:borderw=3:bordercolor=black:x=w-text_w-80:y={y_offset}"
            )
        
        return ",".join(filters)
    
    def _encode_clip_with_title(self, input_path: str, output_path: str,
                               start_time: float = None, duration: float = None,
                               subtitle_file: str = None) -> bool:
        """일반 템플릿용 타이틀이 적용된 클립 인코딩"""
        logger.info(f"_encode_clip_with_title called with subtitle_file: {subtitle_file}")
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # 비디오 필터 구성
        vf_filters = []
        
        # 비율 유지하면서 FHD로 스케일 (letterbox/pillarbox)
        scale_filter = (
            "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
        )
        vf_filters.append(scale_filter)
        
        # 자막 추가
        if subtitle_file and os.path.exists(subtitle_file):
            # FFmpeg ass 필터를 위한 올바른 이스케이핑
            abs_path = os.path.abspath(subtitle_file)
            # Windows 호환을 위해 백슬래시를 슬래시로 변환
            subtitle_path = abs_path.replace('\\', '/')
            # FFmpeg ass 필터를 위한 특수 문자 이스케이핑
            subtitle_path = subtitle_path.replace(':', '\\:').replace('[', '\\[').replace(']', '\\]')
            subtitle_path = subtitle_path.replace(',', '\\,').replace("'", "\\'").replace(' ', '\\ ')
            vf_filters.append(f"ass={subtitle_path}")
            logger.info(f"Adding ASS subtitle filter: ass={subtitle_path}")
        
        # 자막 모드 표시 추가 (일반 템플릿 1, 2, 3에서만)
        current_template = getattr(self, '_current_template_name', '')
        current_subtitle_mode = getattr(self, '_current_subtitle_mode', '')
        
        # 표시할 레이블 가져오기
        mode_label = self.subtitle_mode_labels.get(current_subtitle_mode, '')
        
        # 레이블이 있고, 일반 템플릿인 경우에만 표시
        if mode_label and ('template_1' in current_template or 'template_2' in current_template or 'template_3' in current_template):
            if '_shorts' not in current_template:  # 일반 템플릿만 (쇼츠 제외)
                # 폰트 파일 경로
                font_file = "/home/kang/.fonts/TmonMonsori.ttf"
                if not os.path.exists(font_file):
                    font_file = "NanumGothic"  # 폴백 폰트
                
                # 자막 모드 텍스트 추가 (좌측 상단, 페이드인 효과)
                # 해상도에 따라 폰트 크기 조정 (FHD 기준 70, 비율에 따라 조정)
                mode_text = "drawtext=text='{}':fontfile={}:fontsize='70*min(1,min(w/1920,h/1080))':fontcolor=white@0.8:borderw=3:bordercolor=black:x='80*min(1,min(w/1920,h/1080))':y='80*min(1,min(w/1920,h/1080))':alpha='if(lt(t,0.5),t/0.5,1)'".format(mode_label, font_file)
                vf_filters.append(mode_text)
                logger.info(f"Adding subtitle mode indicator '{mode_label}' for {current_template}")
        
        # 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            vf_filters.append(title_filter)
        
        if vf_filters:
            vf_string = ','.join(vf_filters)
            cmd.extend(['-vf', vf_string])
            logger.info(f"Video filters applied: {vf_string}")
        
        # 인코딩 설정
        encoding_opts = TemplateStandards.get_standard_encoding_options()
        cmd.extend(encoding_opts)
        cmd.append(output_path)
        
        # 실행
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _run_ffmpeg_with_timeout(self, cmd: List[str], timeout: int = 300) -> tuple:
        """타임아웃이 있는 FFmpeg 실행 (5분)"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg command timed out after {timeout} seconds")
            return -1, "", "Command timed out"
        except Exception as e:
            logger.error(f"FFmpeg execution error: {e}")
            return -1, "", str(e)
    
    def _encode_slow_motion_clip(self, input_path: str, output_path: str,
                               start_time: float = None, duration: float = None,
                               subtitle_file: str = None, speed: float = 0.7) -> bool:
        """슬로우 모션 클립 생성"""
        
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            # 슬로우 모션이므로 실제 길이는 duration / speed
            actual_duration = duration / speed
            cmd.extend(['-t', str(actual_duration)])
        
        # 비디오/오디오 필터
        vf_filters = []
        af_filters = []
        
        # 속도 조절 필터
        vf_filters.append(f"setpts={1/speed}*PTS")
        af_filters.append(f"atempo={speed}")
        
        # 자막 추가
        if subtitle_file and os.path.exists(subtitle_file):
            subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
            vf_filters.append(f"ass='{subtitle_path}'")
        
        # 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            vf_filters.append(title_filter)
        
        if vf_filters:
            cmd.extend(['-vf', ','.join(vf_filters)])
        
        if af_filters:
            cmd.extend(['-af', ','.join(af_filters)])
        
        # 인코딩 설정
        cmd.extend([
            '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
            '-preset', TemplateStandards.STANDARD_VIDEO_PRESET,
            '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
            '-profile:v', TemplateStandards.STANDARD_VIDEO_PROFILE,
            '-level', TemplateStandards.STANDARD_VIDEO_LEVEL,
            '-pix_fmt', TemplateStandards.STANDARD_PIX_FMT,
            '-tune', 'film',
            '-r', str(TemplateStandards.STANDARD_FRAMERATE),
            '-vsync', 'cfr',
            '-x264opts', f'keyint={TemplateStandards.STANDARD_GOP_SIZE}:min-keyint=24:scenecut=40:threads=12:lookahead-threads=2:rc-lookahead=20:ref=3:bframes=3:b-adapt=1:me=hex:subme=7',
            '-c:a', TemplateStandards.OUTPUT_AUDIO_CODEC,
            '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
            '-ar', str(TemplateStandards.OUTPUT_SAMPLE_RATE),
            '-ac', str(TemplateStandards.OUTPUT_CHANNELS),
            '-movflags', '+faststart',
            output_path
        ])
        
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _get_face_crop_params(self, video_path: str, start_time: float = None) -> Optional[Tuple[int, int, int, int]]:
        """얼굴 인식을 통한 크롭 영역 계산"""
        if not CV2_AVAILABLE:
            return None
        
        try:
            # 프레임 추출
            cap = cv2.VideoCapture(video_path)
            if start_time:
                cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)
            
            ret, frame = cap.read()
            if not ret:
                cap.release()
                return None
            
            height, width = frame.shape[:2]
            
            # DNN 기반 얼굴 인식 (더 정확함)
            # OpenCV의 pre-trained 모델 사용
            model_path = "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
            
            if os.path.exists(model_path):
                # Haar Cascade 사용 (빠르지만 정확도 낮음)
                face_cascade = cv2.CascadeClassifier(model_path)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                if len(faces) > 0:
                    # 가장 큰 얼굴 선택
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    
                    # 얼굴 중심 계산
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # 9:16 비율로 크롭 영역 계산
                    crop_height = height
                    crop_width = int(height * 9 / 16)
                    
                    # 얼굴이 중앙에 오도록 조정
                    crop_x = max(0, min(width - crop_width, center_x - crop_width // 2))
                    crop_y = 0
                    
                    cap.release()
                    return (crop_x, crop_y, crop_width, crop_height)
            
            cap.release()
            return None
            
        except Exception as e:
            logger.warning(f"Face detection failed: {e}")
            return None