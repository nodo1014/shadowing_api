"""
Template-based video encoder
"""
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from .encoder import VideoEncoder
from .ffmpeg_utils import create_still_frame_video, extract_clip, add_subtitles, concatenate_videos

logger = logging.getLogger(__name__)


class TemplateVideoEncoder(VideoEncoder):
    """Template-based video encoder for shadowing patterns"""
    
    def __init__(self):
        super().__init__()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Load template configurations"""
        template_path = Path(__file__).parent.parent.parent.parent / "templates" / "shadowing_patterns.json"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('patterns', {})
        
        logger.warning(f"Template file not found: {template_path}")
        return self._get_default_templates()
    
    def _get_default_templates(self) -> Dict:
        """Get default template configurations"""
        return {
            "template_1": {
                "name": "Progressive Learning",
                "description": "5단계 점진적 학습",
                "clips": [
                    {"subtitle_mode": "no_subtitle", "folder_name": "1_nosub", "count": 1, "subtitle_type": None},
                    {"subtitle_mode": "blank_subtitle", "folder_name": "2_blank", "count": 1, "subtitle_type": "blank"},
                    {"subtitle_mode": "blank_with_korean", "folder_name": "3_blank_kor", "count": 1, "subtitle_type": "blank_korean"},
                    {"subtitle_mode": "both_subtitle", "folder_name": "4_both", "count": 1, "subtitle_type": "full"},
                    {"subtitle_mode": "no_subtitle", "folder_name": "5_nosub", "count": 1, "subtitle_type": None}
                ],
                "gap_duration": 1.5
            },
            "template_2": {
                "name": "Keyword Focus",
                "description": "키워드 집중 학습",
                "clips": [
                    {"subtitle_mode": "no_subtitle", "folder_name": "1_nosub", "count": 1, "subtitle_type": None},
                    {"subtitle_mode": "blank_subtitle", "folder_name": "2_blank", "count": 1, "subtitle_type": "blank"},
                    {"subtitle_mode": "full_subtitle", "folder_name": "4_full", "count": 2, "subtitle_type": "full"}
                ],
                "gap_duration": 1.5
            },
            "template_3": {
                "name": "Classic Pattern",
                "description": "전통적 학습 패턴",
                "clips": [
                    {"subtitle_mode": "no_subtitle", "folder_name": "1_nosub", "count": 2, "subtitle_type": None},
                    {"subtitle_mode": "blank_with_korean", "folder_name": "2_blank_kor", "count": 2, "subtitle_type": "blank_korean"},
                    {"subtitle_mode": "both_subtitle", "folder_name": "3_both", "count": 2, "subtitle_type": "full"}
                ],
                "gap_duration": 2.0
            }
        }
    
    def create_from_template(
        self,
        template_name: str,
        media_path: str,
        subtitle_data: Dict,
        output_path: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        padding_before: float = 0.5,
        padding_after: float = 0.5,
        save_individual_clips: bool = True,
        subtitle_files: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Create video using template
        
        Args:
            template_name: Name of template to use
            media_path: Input video path
            subtitle_data: Subtitle data dictionary
            output_path: Output video path
            start_time: Start time in seconds
            end_time: End time in seconds
            padding_before: Padding before start
            padding_after: Padding after end
            save_individual_clips: Save individual clips
            subtitle_files: Pre-generated subtitle files
            
        Returns:
            True if successful, False otherwise
        """
        if template_name not in self.templates:
            logger.error(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        logger.info(f"Using template: {template['name']} - {template['description']}")
        
        try:
            # Calculate padded times
            if start_time is not None and end_time is not None:
                padded_start = max(0, start_time - padding_before)
                padded_end = end_time + padding_after
                duration = padded_end - padded_start
            else:
                padded_start = None
                duration = None
            
            # Ensure subtitle data has timing info
            if 'start_time' not in subtitle_data:
                subtitle_data['start_time'] = 0.0
            if 'end_time' not in subtitle_data:
                subtitle_data['end_time'] = duration if duration else 5.0
            
            # Get gap duration from template
            gap_duration = template.get('gap_duration', 1.5)
            
            # Prepare subtitle files if not provided
            if not subtitle_files:
                subtitle_files = self._prepare_subtitle_files(
                    subtitle_data, template_name, duration, gap_duration
                )
            
            # Create clips based on template
            temp_clips = []
            clip_base_dir = None
            
            if save_individual_clips:
                clip_base_dir = Path(output_path).parent / "individual_clips"
                clip_base_dir.mkdir(parents=True, exist_ok=True)
            
            clip_number = Path(output_path).stem.split('_')[-1] if '_' in Path(output_path).stem else '0000'
            
            for clip_config in template['clips']:
                for i in range(clip_config['count']):
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_clips.append(temp_file.name)
                    temp_file.close()
                    
                    # Get subtitle file for this clip
                    subtitle_file = subtitle_files.get(clip_config['subtitle_type']) if clip_config['subtitle_type'] else None
                    
                    # Check if this clip should use still frame mode
                    video_mode = clip_config.get('video_mode', 'normal')
                    
                    # Encode the clip based on video mode
                    if video_mode == 'still_frame':
                        success = create_still_frame_video(
                            media_path, temp_clips[-1],
                            padded_start + 0.1 if padded_start else 0.1,
                            duration if duration else 5.0,
                            subtitle_file
                        )
                    else:
                        # Extract clip first
                        if padded_start is not None and duration is not None:
                            success = extract_clip(
                                media_path, temp_clips[-1],
                                padded_start, duration
                            )
                        else:
                            # Full video
                            import shutil
                            shutil.copy2(media_path, temp_clips[-1])
                            success = True
                        
                        # Add subtitles if needed
                        if success and subtitle_file:
                            temp_raw = temp_clips[-1]
                            temp_with_sub = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                            temp_with_sub.close()
                            
                            success = add_subtitles(
                                temp_raw, temp_with_sub.name,
                                subtitle_file
                            )
                            
                            if success:
                                Path(temp_raw).unlink(missing_ok=True)
                                temp_clips[-1] = temp_with_sub.name
                            else:
                                Path(temp_with_sub.name).unlink(missing_ok=True)
                    
                    if not success:
                        raise Exception(f"Failed to create {clip_config['subtitle_mode']} clip")
                    
                    # Save individual clip if requested
                    if save_individual_clips and clip_base_dir:
                        folder_name = clip_config.get('folder_name', clip_config['subtitle_mode'])
                        self._save_individual_clip(
                            temp_clips[-1], clip_base_dir,
                            folder_name, i + 1, clip_number
                        )
                    
                    logger.info(f"Created {clip_config['subtitle_mode']} clip {i+1}/{clip_config['count']}")
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Concatenate clips with gaps
            success = concatenate_videos(
                temp_clips, output_path, gap_duration
            )
            
            if not success:
                raise Exception("Failed to concatenate clips")
            
            logger.info(f"Successfully created template video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating video from template: {e}", exc_info=True)
            return False
            
        finally:
            # Clean up temp clips
            for temp_clip in temp_clips:
                Path(temp_clip).unlink(missing_ok=True)
            
            # Clean up subtitle files if we created them
            if subtitle_files:
                for subtitle_file in subtitle_files.values():
                    if subtitle_file:
                        Path(subtitle_file).unlink(missing_ok=True)
    
    def _prepare_subtitle_files(
        self,
        subtitle_data: Dict,
        template_name: str,
        clip_duration: Optional[float] = None,
        gap_duration: float = 0.0
    ) -> Dict[str, str]:
        """Prepare subtitle files for template"""
        subtitle_files = {}
        
        # Import subtitle generator
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent.parent.parent))
        from subtitle_generator import SubtitleGenerator
        
        generator = SubtitleGenerator()
        
        template = self.templates.get(template_name)
        if not template:
            return subtitle_files
        
        # Get needed subtitle types
        needed_types = set()
        for clip in template['clips']:
            if clip['subtitle_type']:
                needed_types.add(clip['subtitle_type'])
        
        # Generate subtitle files
        for subtitle_type in needed_types:
            temp_file = tempfile.NamedTemporaryFile(suffix=f'_{subtitle_type}.ass', delete=False)
            temp_file.close()
            
            try:
                if subtitle_type == 'full':
                    with_keywords = (template_name == "template_2")
                    generator.generate_full_subtitle(
                        subtitle_data, temp_file.name,
                        with_keywords=with_keywords,
                        clip_duration=clip_duration,
                        gap_duration=gap_duration
                    )
                elif subtitle_type == 'blank':
                    generator.generate_blank_subtitle(
                        subtitle_data, temp_file.name,
                        with_korean=False,
                        clip_duration=clip_duration,
                        gap_duration=gap_duration
                    )
                elif subtitle_type == 'blank_korean':
                    generator.generate_blank_subtitle(
                        subtitle_data, temp_file.name,
                        with_korean=True,
                        clip_duration=clip_duration,
                        gap_duration=gap_duration
                    )
                elif subtitle_type == 'korean':
                    generator.generate_korean_only_subtitle(
                        subtitle_data, temp_file.name,
                        clip_duration=clip_duration,
                        gap_duration=gap_duration
                    )
                
                subtitle_files[subtitle_type] = temp_file.name
                
            except Exception as e:
                logger.error(f"Failed to generate {subtitle_type} subtitle: {e}")
                Path(temp_file.name).unlink(missing_ok=True)
        
        return subtitle_files