"""
Video encoder adapter for backward compatibility
Redirects old video_encoder.py calls to new modular structure
"""
from shadowing_maker.core.video.encoder import VideoEncoder as _VideoEncoder
from shadowing_maker.core.video.template_encoder import TemplateVideoEncoder as _TemplateVideoEncoder
from shadowing_maker.core.subtitle.generator import SubtitleGenerator as _SubtitleGenerator
import logging

logger = logging.getLogger(__name__)


class VideoEncoder(_VideoEncoder):
    """Backward compatible VideoEncoder"""
    
    def __init__(self):
        super().__init__()
        self.process_timeout = 300  # Default timeout
    
    def create_shadowing_video(self, media_path, ass_path, output_path, 
                              start_time=None, end_time=None,
                              padding_before=0.5, padding_after=0.5,
                              save_individual_clips=False, subtitle_data=None):
        """Create shadowing video (backward compatible)"""
        # If subtitle_data is provided, use it directly
        # Otherwise try to load from ASS file
        subtitle_files = {}
        
        if subtitle_data:
            # Generate subtitle files from data
            from tempfile import NamedTemporaryFile
            
            # Generate full subtitle
            if self.pattern.get("both_subtitle", 0) > 0:
                full_file = NamedTemporaryFile(suffix='_full.ass', delete=False)
                full_file.close()
                gen = _SubtitleGenerator()
                gen.generate_full_subtitle(subtitle_data, full_file.name)
                subtitle_files["full"] = full_file.name
            
            # Generate Korean subtitle if needed
            if self.pattern.get("korean_with_note", 0) > 0:
                korean_file = NamedTemporaryFile(suffix='_korean.ass', delete=False)
                korean_file.close()
                gen = _SubtitleGenerator()
                gen.generate_korean_only_subtitle(subtitle_data, korean_file.name)
                subtitle_files["korean"] = korean_file.name
        elif ass_path and ass_path != "temp.ass":
            # Use provided ASS file
            subtitle_files["full"] = ass_path
            subtitle_files["korean"] = ass_path
        
        try:
            # Call parent method with new parameters
            return super().create_shadowing_video(
                media_path=media_path,
                output_path=output_path,
                start_time=start_time,
                end_time=end_time,
                subtitle_data=subtitle_data,
                subtitle_files=subtitle_files,
                save_individual_clips=save_individual_clips,
                padding_before=padding_before,
                padding_after=padding_after
            )
        finally:
            # Cleanup temp subtitle files
            from pathlib import Path
            for file_path in subtitle_files.values():
                if file_path and file_path != ass_path:
                    Path(file_path).unlink(missing_ok=True)
    
    def _encode_clip(self, input_path, output_path, start_time, duration, subtitle_file=None):
        """Encode clip (backward compatible)"""
        from shadowing_maker.core.video.ffmpeg_utils import extract_clip, add_subtitles
        
        # First extract the clip
        success = extract_clip(
            input_path, output_path,
            start_time, duration,
            preset=self.encoding_settings["no_subtitle"]["preset"],
            crf=self.encoding_settings["no_subtitle"]["crf"]
        )
        
        # Add subtitles if provided
        if success and subtitle_file:
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_file.close()
            
            # Move extracted clip to temp
            import shutil
            shutil.move(output_path, temp_file.name)
            
            # Add subtitles
            success = add_subtitles(
                temp_file.name, output_path, subtitle_file,
                width=self.encoding_settings["with_subtitle"]["width"],
                height=self.encoding_settings["with_subtitle"]["height"]
            )
            
            # Cleanup
            Path(temp_file.name).unlink(missing_ok=True)
        
        return success
    
    def _concatenate_clips(self, clip_paths, output_path, gap_duration=0.5):
        """Concatenate clips (backward compatible)"""
        # Use parent class implementation for freeze frame support
        logger.debug(f"[DEBUG] _concatenate_clips called with {len(clip_paths)} clips, gap_duration={gap_duration}")
        # Check if parent class has the method
        if hasattr(super(), '_concatenate_clips'):
            return super()._concatenate_clips(clip_paths, output_path, gap_duration)
        else:
            # Fallback to ffmpeg_utils if parent doesn't have it
            from shadowing_maker.core.video.ffmpeg_utils import concatenate_videos
            return concatenate_videos(clip_paths, output_path, gap_duration)
    
    def _run_ffmpeg_with_timeout(self, cmd, timeout=None):
        """Run FFmpeg with timeout (backward compatible)"""
        from shadowing_maker.core.video.ffmpeg_utils import run_ffmpeg_command
        
        if timeout is None:
            timeout = self.process_timeout
        
        return run_ffmpeg_command(cmd, timeout)


class TemplateVideoEncoder(_TemplateVideoEncoder):
    """Backward compatible TemplateVideoEncoder"""
    
    def __init__(self):
        super().__init__()
        # Import subtitle generator for backward compatibility
        self.subtitle_generator = _SubtitleGenerator()
    
    def _encode_still_frame_clip(self, input_path, output_path, start_time, duration, subtitle_file=None):
        """Encode still frame clip (backward compatible)"""
        from shadowing_maker.core.video.ffmpeg_utils import create_still_frame_video
        
        frame_time = start_time + 0.1 if start_time else 0.1
        return create_still_frame_video(
            input_path, output_path,
            frame_time, duration,
            subtitle_file
        )


# Export SubtitleGenerator for backward compatibility
SubtitleGenerator = _SubtitleGenerator