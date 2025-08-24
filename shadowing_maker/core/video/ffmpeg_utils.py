"""
FFmpeg utility functions
"""
import subprocess
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """FFmpeg execution error"""
    pass


def run_ffmpeg_command(cmd: List[str], timeout: int = 300) -> Tuple[int, str, str]:
    """
    Run FFmpeg command with timeout
    
    Args:
        cmd: FFmpeg command as list
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
        
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise FFmpegError(f"FFmpeg command timed out after {timeout} seconds")
    except Exception as e:
        raise FFmpegError(f"FFmpeg execution failed: {e}")


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Get video information using ffprobe
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary containing video information
    """
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        video_path
    ]
    
    returncode, stdout, stderr = run_ffmpeg_command(cmd, timeout=30)
    
    if returncode != 0:
        raise FFmpegError(f"Failed to probe video: {stderr}")
    
    try:
        data = json.loads(stdout)
        video_stream = next(
            (s for s in data['streams'] if s['codec_type'] == 'video'),
            None
        )
        audio_stream = next(
            (s for s in data['streams'] if s['codec_type'] == 'audio'),
            None
        )
        
        return {
            'video': video_stream,
            'audio': audio_stream,
            'streams': data['streams']
        }
    except (json.JSONDecodeError, KeyError) as e:
        raise FFmpegError(f"Failed to parse video info: {e}")


def extract_clip(
    input_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    video_codec: str = 'libx264',
    audio_codec: str = 'aac',
    crf: str = '18',
    preset: str = 'medium'
) -> bool:
    """
    Extract a clip from video
    
    Args:
        input_path: Input video path
        output_path: Output video path
        start_time: Start time in seconds
        duration: Duration in seconds
        video_codec: Video codec
        audio_codec: Audio codec
        crf: Constant Rate Factor for quality
        preset: Encoding preset
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', input_path,
        '-t', str(duration),
        '-c:v', video_codec,
        '-preset', preset,
        '-crf', crf,
        '-pix_fmt', 'yuv420p',
        '-c:a', audio_codec,
        '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    
    returncode, _, stderr = run_ffmpeg_command(cmd)
    
    if returncode != 0:
        logger.error(f"Failed to extract clip: {stderr}")
        return False
    
    return True


def add_subtitles(
    input_path: str,
    output_path: str,
    subtitle_path: str,
    width: int = 1920,
    height: int = 1080
) -> bool:
    """
    Add subtitles to video
    
    Args:
        input_path: Input video path
        output_path: Output video path
        subtitle_path: ASS subtitle file path
        width: Output width
        height: Output height
        
    Returns:
        True if successful, False otherwise
    """
    # Escape subtitle path for FFmpeg filter
    subtitle_escaped = str(Path(subtitle_path).absolute())
    subtitle_escaped = subtitle_escaped.replace('\\', '/').replace(':', '\\:')
    subtitle_escaped = subtitle_escaped.replace('[', '\\[').replace(']', '\\]')
    subtitle_escaped = subtitle_escaped.replace(',', '\\,').replace("'", "\\'")
    
    video_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,ass={subtitle_escaped}"
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', video_filter,
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    
    returncode, _, stderr = run_ffmpeg_command(cmd)
    
    if returncode != 0:
        logger.error(f"Failed to add subtitles: {stderr}")
        return False
    
    return True


def concatenate_videos(
    video_paths: List[str],
    output_path: str,
    gap_duration: float = 0.0
) -> bool:
    """
    Concatenate multiple videos with optional gaps
    
    Args:
        video_paths: List of video paths to concatenate
        output_path: Output video path
        gap_duration: Gap duration between videos in seconds
        
    Returns:
        True if successful, False otherwise
    """
    if not video_paths:
        logger.error("No videos to concatenate")
        return False
    
    if len(video_paths) == 1:
        # Just copy single video
        import shutil
        shutil.copy2(video_paths[0], output_path)
        return True
    
    # Create concat file
    concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    temp_gaps = []
    
    try:
        # Get first video info for gap creation
        if gap_duration > 0:
            video_info = get_video_info(video_paths[0])
            if video_info['video']:
                width = video_info['video']['width']
                height = video_info['video']['height']
        
        # Write concat list
        for i, video_path in enumerate(video_paths):
            escaped_path = video_path.replace('\\', '/').replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
            
            # Add gap after each video (except last)
            if gap_duration > 0 and i < len(video_paths) - 1:
                gap_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                gap_file.close()
                temp_gaps.append(gap_file.name)
                
                # Create black video gap
                gap_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi',
                    '-i', f'color=black:size={width}x{height}:duration={gap_duration}',
                    '-f', 'lavfi',
                    '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                    '-t', str(gap_duration),
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '18',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    gap_file.name
                ]
                
                returncode, _, _ = run_ffmpeg_command(gap_cmd)
                if returncode == 0:
                    escaped_gap = gap_file.name.replace('\\', '/').replace("'", "'\\''")
                    concat_file.write(f"file '{escaped_gap}'\n")
        
        concat_file.close()
        
        # Concatenate videos
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file.name,
            '-c', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
        
        returncode, _, stderr = run_ffmpeg_command(cmd)
        
        if returncode != 0:
            logger.error(f"Failed to concatenate videos: {stderr}")
            return False
        
        return True
        
    finally:
        # Cleanup
        Path(concat_file.name).unlink(missing_ok=True)
        for gap_file in temp_gaps:
            Path(gap_file).unlink(missing_ok=True)


def create_still_frame_video(
    input_path: str,
    output_path: str,
    frame_time: float,
    duration: float,
    subtitle_path: Optional[str] = None
) -> bool:
    """
    Create a video with still frame from specific time
    
    Args:
        input_path: Input video path
        output_path: Output video path
        frame_time: Time to extract frame from
        duration: Duration of output video
        subtitle_path: Optional subtitle file
        
    Returns:
        True if successful, False otherwise
    """
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
        img_path = img_file.name
    
    try:
        # Extract frame
        extract_cmd = [
            'ffmpeg', '-y',
            '-ss', str(frame_time),
            '-i', input_path,
            '-vframes', '1',
            '-q:v', '2',
            img_path
        ]
        
        returncode, _, stderr = run_ffmpeg_command(extract_cmd)
        if returncode != 0:
            logger.error(f"Failed to extract frame: {stderr}")
            return False
        
        # Create video from still frame
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-framerate', '30',
            '-i', img_path,
            '-ss', str(frame_time),
            '-i', input_path,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '16',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v',
            '-map', '1:a'
        ]
        
        # Add subtitle if provided
        if subtitle_path and Path(subtitle_path).exists():
            subtitle_escaped = str(Path(subtitle_path).absolute())
            subtitle_escaped = subtitle_escaped.replace('\\', '/').replace(':', '\\:')
            subtitle_escaped = subtitle_escaped.replace('[', '\\[').replace(']', '\\]')
            subtitle_escaped = subtitle_escaped.replace(',', '\\,').replace("'", "\\'")
            cmd.extend(['-vf', f"ass={subtitle_escaped}"])
        
        cmd.extend([
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ])
        
        returncode, _, stderr = run_ffmpeg_command(cmd)
        
        if returncode != 0:
            logger.error(f"Failed to create still frame video: {stderr}")
            return False
        
        return True
        
    finally:
        Path(img_path).unlink(missing_ok=True)