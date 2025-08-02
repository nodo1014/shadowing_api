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
        
        # Prepare subtitle files
        subtitle_files = self._prepare_subtitle_files(subtitle_data, template_name)
        
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
                    
                    # Encode the clip
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
    
    def _prepare_subtitle_files(self, subtitle_data: Dict, template_name: str) -> Dict[str, str]:
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
        
        # 필요한 자막 파일들 생성
        for subtitle_type in needed_types:
            if subtitle_type == 'full':
                # Full subtitle (with keywords for template_2)
                full_ass = tempfile.NamedTemporaryFile(suffix='_full.ass', delete=False)
                full_ass.close()
                with_keywords = (template_name == "template_2")
                self.subtitle_generator.generate_full_subtitle(subtitle_data, full_ass.name, with_keywords=with_keywords)
                subtitle_files['full'] = full_ass.name
                
            elif subtitle_type == 'blank':
                # Blank subtitle
                blank_ass = tempfile.NamedTemporaryFile(suffix='_blank.ass', delete=False)
                blank_ass.close()
                self.subtitle_generator.generate_blank_subtitle(subtitle_data, blank_ass.name, with_korean=False)
                subtitle_files['blank'] = blank_ass.name
                
            elif subtitle_type == 'korean':
                # Korean only subtitle
                korean_ass = tempfile.NamedTemporaryFile(suffix='_korean.ass', delete=False)
                korean_ass.close()
                self.subtitle_generator.generate_korean_only_subtitle(subtitle_data, korean_ass.name)
                subtitle_files['korean'] = korean_ass.name
                
            elif subtitle_type == 'blank_korean':
                # Blank English with Korean subtitle
                blank_korean_ass = tempfile.NamedTemporaryFile(suffix='_blank_korean.ass', delete=False)
                blank_korean_ass.close()
                self.subtitle_generator.generate_blank_subtitle(subtitle_data, blank_korean_ass.name, with_korean=True)
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