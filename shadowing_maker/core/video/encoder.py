"""
Base video encoder
"""
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .ffmpeg_utils import (
    extract_clip, add_subtitles, concatenate_videos,
    create_still_frame_video, get_video_info
)

logger = logging.getLogger(__name__)


class VideoEncoder:
    """Base video encoder with shadowing pattern support"""
    
    def __init__(self):
        self.encoding_settings = {
            "no_subtitle": {
                "width": 1920,
                "height": 1080,
                "video_codec": "libx264",
                "audio_codec": "aac",
                "preset": "medium",
                "crf": "18",
                "profile": "high",
                "level": "4.1",
                "pix_fmt": "yuv420p",
                "audio_bitrate": "192k",
                "tune": "film",
                "x264opts": "keyint=240:min-keyint=24:scenecut=40"
            },
            "with_subtitle": {
                "width": 1920,
                "height": 1080,
                "video_codec": "libx264",
                "audio_codec": "aac",
                "preset": "medium",
                "crf": "16",
                "profile": "high",
                "level": "4.1",
                "pix_fmt": "yuv420p",
                "audio_bitrate": "192k",
                "tune": "film",
                "x264opts": "keyint=240:min-keyint=24:scenecut=40"
            }
        }
        
        # Default pattern
        self.pattern = {
            "no_subtitle": 1,
            "korean_with_note": 0,
            "both_subtitle": 3
        }
    
    def set_pattern(self, no_sub: int, korean: int, both: int):
        """Set shadowing pattern"""
        self.pattern = {
            "no_subtitle": no_sub,
            "korean_with_note": korean,
            "both_subtitle": both
        }
    
    def create_shadowing_video(
        self,
        media_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        subtitle_data: Optional[Dict] = None,
        subtitle_files: Optional[Dict[str, str]] = None,
        save_individual_clips: bool = False,
        padding_before: float = 0.5,
        padding_after: float = 0.5
    ) -> bool:
        """
        Create shadowing video with pattern
        
        Args:
            media_path: Input video path
            output_path: Output video path
            start_time: Start time in seconds
            end_time: End time in seconds
            subtitle_data: Subtitle data dictionary
            subtitle_files: Pre-generated subtitle files
            save_individual_clips: Save individual clips
            padding_before: Padding before start
            padding_after: Padding after end
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate padded times
            padded_start = max(0, start_time - padding_before)
            padded_end = end_time + padding_after
            duration = padded_end - padded_start
            
            temp_clips = []
            
            # Create output directory
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create clips subfolder if needed
            if save_individual_clips:
                clips_dir = output_dir / "individual_clips"
                clips_dir.mkdir(exist_ok=True)
            
            clip_number = Path(output_path).stem.split('_')[-1] if '_' in Path(output_path).stem else '0000'
            
            # 1. Create no-subtitle clips
            for i in range(self.pattern["no_subtitle"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                success = extract_clip(
                    media_path, temp_clips[-1],
                    padded_start, duration
                )
                
                if not success:
                    raise Exception(f"Failed to create no-subtitle clip {i+1}")
                
                if save_individual_clips:
                    self._save_individual_clip(
                        temp_clips[-1], clips_dir,
                        "1_nosub", i + 1, clip_number
                    )
                
                logger.info(f"Created no-subtitle clip {i+1}/{self.pattern['no_subtitle']}")
            
            # 2. Create korean subtitle clips
            for i in range(self.pattern["korean_with_note"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                if subtitle_files and "korean" in subtitle_files:
                    # First extract, then add subtitles
                    temp_raw = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_raw.close()
                    
                    success = extract_clip(
                        media_path, temp_raw.name,
                        padded_start, duration
                    )
                    
                    if success:
                        success = add_subtitles(
                            temp_raw.name, temp_clips[-1],
                            subtitle_files["korean"]
                        )
                    
                    Path(temp_raw.name).unlink(missing_ok=True)
                else:
                    success = extract_clip(
                        media_path, temp_clips[-1],
                        padded_start, duration
                    )
                
                if not success:
                    raise Exception(f"Failed to create korean subtitle clip {i+1}")
                
                if save_individual_clips:
                    self._save_individual_clip(
                        temp_clips[-1], clips_dir,
                        "2_korean", i + 1, clip_number
                    )
                
                logger.info(f"Created korean subtitle clip {i+1}/{self.pattern['korean_with_note']}")
            
            # 3. Create both subtitle clips
            for i in range(self.pattern["both_subtitle"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                if subtitle_files and "full" in subtitle_files:
                    # First extract, then add subtitles
                    temp_raw = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_raw.close()
                    
                    success = extract_clip(
                        media_path, temp_raw.name,
                        padded_start, duration
                    )
                    
                    if success:
                        success = add_subtitles(
                            temp_raw.name, temp_clips[-1],
                            subtitle_files["full"]
                        )
                    
                    Path(temp_raw.name).unlink(missing_ok=True)
                else:
                    success = extract_clip(
                        media_path, temp_clips[-1],
                        padded_start, duration
                    )
                
                if not success:
                    raise Exception(f"Failed to create both subtitle clip {i+1}")
                
                if save_individual_clips:
                    self._save_individual_clip(
                        temp_clips[-1], clips_dir,
                        "3_both", i + 1, clip_number
                    )
                
                logger.info(f"Created both subtitle clip {i+1}/{self.pattern['both_subtitle']}")
            
            # Concatenate all clips with gaps
            success = concatenate_videos(
                temp_clips, output_path,
                gap_duration=1.5
            )
            
            if not success:
                raise Exception("Failed to concatenate clips")
            
            logger.info(f"Successfully created shadowing video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating shadowing video: {e}")
            return False
            
        finally:
            # Cleanup temp files
            for temp_clip in temp_clips:
                Path(temp_clip).unlink(missing_ok=True)
    
    def _save_individual_clip(
        self,
        clip_path: str,
        base_dir: Path,
        folder_name: str,
        index: int,
        clip_number: str
    ):
        """Save individual clip to folder"""
        import shutil
        
        sub_dir = base_dir / folder_name
        sub_dir.mkdir(exist_ok=True)
        
        dest_file = sub_dir / f"clip_{clip_number}_{index}.mp4"
        shutil.copy2(clip_path, str(dest_file))
        logger.debug(f"Saved: {dest_file.relative_to(base_dir)}")