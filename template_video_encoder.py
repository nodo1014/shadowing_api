"""
Template-based video encoder
템플릿 기반으로 shadowing 비디오를 생성하는 개선된 인코더
"""
import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional
from video_encoder import VideoEncoder
from subtitle_generator import SubtitleGenerator

logger = logging.getLogger(__name__)


class TemplateVideoEncoder(VideoEncoder):
    """템플릿 기반 비디오 인코더"""
    
    def __init__(self):
        super().__init__()
        self.subtitle_generator = SubtitleGenerator()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """템플릿 파일 로드"""
        template_path = Path(__file__).parent / "templates" / "shadowing_patterns.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('patterns', {})
        return {}
    
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
            
            for clip_config in template['clips']:
                for i in range(clip_config['count']):
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_clips.append(temp_file.name)
                    temp_file.close()
                    
                    # Get subtitle file for this clip
                    subtitle_file = subtitle_files.get(clip_config['subtitle_type'])
                    
                    # Check if this clip should use still frame mode
                    video_mode = clip_config.get('video_mode', 'normal')
                    
                    # Encode the clip based on video mode
                    if video_mode == 'still_frame':
                        if not self._encode_still_frame_clip(media_path, temp_clips[-1],
                                                           padded_start, duration,
                                                           subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create still frame {clip_config['subtitle_mode']} clip")
                    else:
                        if not self._encode_clip(media_path, temp_clips[-1],
                                               padded_start, duration,
                                               subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create {clip_config['subtitle_mode']} clip")
                    
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
            if not self._concatenate_clips(temp_clips, output_path, gap_duration):
                raise Exception("Failed to concatenate clips")
            
            logger.info(f"Successfully created shadowing video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating video from template: {e}", exc_info=True)
            return False
            
        finally:
            # Clean up
            for temp_clip in temp_clips:
                if os.path.exists(temp_clip):
                    os.unlink(temp_clip)
            
            # Clean up subtitle files
            for subtitle_file in subtitle_files.values():
                if subtitle_file and os.path.exists(subtitle_file):
                    os.unlink(subtitle_file)
    
    def _prepare_subtitle_files(self, subtitle_data: Dict, template_name: str, clip_duration: float = None, gap_duration: float = 0.0) -> Dict[str, str]:
        """템플릿에 필요한 자막 파일들을 준비"""
        subtitle_files = {}
        
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
        
        # 필요한 자막 파일들 생성
        for subtitle_type in needed_types:
            if subtitle_type == 'full':
                # Full subtitle (with keywords for template_2)
                full_ass = tempfile.NamedTemporaryFile(suffix='_full.ass', delete=False)
                full_ass.close()
                with_keywords = (template_name == "template_2")
                self.subtitle_generator.generate_full_subtitle(subtitle_data, full_ass.name, with_keywords=with_keywords, clip_duration=clip_duration, gap_duration=gap_duration)
                subtitle_files['full'] = full_ass.name
                
            elif subtitle_type == 'blank':
                # Blank subtitle
                blank_ass = tempfile.NamedTemporaryFile(suffix='_blank.ass', delete=False)
                blank_ass.close()
                self.subtitle_generator.generate_blank_subtitle(subtitle_data, blank_ass.name, with_korean=False, clip_duration=clip_duration, gap_duration=gap_duration)
                subtitle_files['blank'] = blank_ass.name
                
            elif subtitle_type == 'korean':
                # Korean only subtitle
                korean_ass = tempfile.NamedTemporaryFile(suffix='_korean.ass', delete=False)
                korean_ass.close()
                self.subtitle_generator.generate_korean_only_subtitle(subtitle_data, korean_ass.name, clip_duration=clip_duration, gap_duration=gap_duration)
                subtitle_files['korean'] = korean_ass.name
                
            elif subtitle_type == 'blank_korean':
                # Blank English with Korean subtitle
                blank_korean_ass = tempfile.NamedTemporaryFile(suffix='_blank_korean.ass', delete=False)
                blank_korean_ass.close()
                self.subtitle_generator.generate_blank_subtitle(subtitle_data, blank_korean_ass.name, with_korean=True, clip_duration=clip_duration, gap_duration=gap_duration)
                subtitle_files['blank_korean'] = blank_korean_ass.name
                
            # 향후 새로운 subtitle_type 추가 시 여기에 elif 추가
            # elif subtitle_type == 'english_only':
            #     ...
        
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
    
    def _encode_still_frame_clip(self, input_path: str, output_path: str,
                                start_time: float = None, duration: float = None,
                                subtitle_file: str = None) -> bool:
        """정지화면 클립 생성 - 첫 프레임을 고정하고 오디오와 자막 유지"""
        import subprocess
        import tempfile
        import os
        
        try:
            # 시작 시점의 프레임 추출
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
                img_path = img_file.name
            
            # 프레임 추출 (시작 시점에서 0.1초 후)
            extract_time = start_time + 0.1 if start_time else 0.1
            
            extract_cmd = [
                'ffmpeg', '-y',
                '-ss', str(extract_time),
                '-i', input_path,
                '-vframes', '1',
                '-q:v', '2',
                img_path
            ]
            
            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to extract frame: {result.stderr}")
                return False
            
            # 정지화면과 오디오 결합
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-framerate', '30',
                '-i', img_path
            ]
            
            # 오디오 추가
            if start_time is not None:
                cmd.extend(['-ss', str(start_time)])
            cmd.extend(['-i', input_path])
            
            if duration is not None:
                cmd.extend(['-t', str(duration)])
            
            # 비디오 설정 (FFmpeg 최적화 옵션 유지)
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                '-profile:v', 'high',
                '-level', '4.1',
                '-pix_fmt', 'yuv420p',
                '-tune', 'film',
                '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
                '-r', '30'
            ])
            
            # 오디오 설정
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '192k',
                '-af', 'aresample=async=1',
                '-map', '0:v',
                '-map', '1:a'
            ])
            
            # 자막 추가
            if subtitle_file and os.path.exists(subtitle_file):
                subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
                cmd.extend(['-vf', f"ass='{subtitle_path}'"])
            
            cmd.extend([
                '-shortest',
                '-movflags', '+faststart',
                output_path
            ])
            
            logger.debug(f"Creating still frame clip: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 임시 이미지 파일 삭제
            os.unlink(img_path)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            logger.info("Still frame clip created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating still frame clip: {e}", exc_info=True)
            return False