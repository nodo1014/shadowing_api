import subprocess
import os
import tempfile
import json
import signal
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VideoEncoder:
    def __init__(self):
        self.process_timeout = 300  # 5 minutes timeout for FFmpeg operations
        # FFmpeg encoding settings based on ffmpeg_ass설정값.md
        self.encoding_settings = {
            "no_subtitle": {
                "video_codec": "libx264",
                "preset": "medium",  # 품질/속도 균형: ultrafast -> medium
                "crf": "16",  # 품질 개선: 16 -> 18 (적절한 품질/파일크기 균형)
                "profile": "high",
                "level": "4.1",
                "pix_fmt": "yuv420p",
                "width": "1920",
                "height": "1080",
                "audio_codec": "aac",
                "audio_bitrate": "192k",
                # 추가 품질 옵션
                "x264opts": "keyint=240:min-keyint=24:scenecut=40",
                "tune": "film"  # 영화/드라마에 최적화
            },
            "with_subtitle": {
                "video_codec": "libx264",
                "preset": "medium",  # 품질/속도 균형: ultrafast -> medium
                "crf": "16",  # 동일한 품질 유지
                "profile": "high",
                "level": "4.1",
                "pix_fmt": "yuv420p",
                "width": "1920",
                "height": "1080",
                "audio_codec": "aac",
                "audio_bitrate": "192k",
                # 추가 품질 옵션
                "x264opts": "keyint=240:min-keyint=24:scenecut=40",
                "tune": "film"  # 영화/드라마에 최적화
            }
        }
        
        # Shadowing pattern 
        # Type 1: 무자막 2회, 영한자막 2회
        # Type 2: 무자막 2회, 키워드 공백 2회, 영한+노트 2회
        self.pattern = {
            "no_subtitle": 2,
            "korean_with_note": 2,
            "both_subtitle": 2
        }
    
    def _run_ffmpeg_with_timeout(self, cmd: List[str], timeout: int = None) -> tuple:
        """Run FFmpeg command with timeout and proper cleanup"""
        if timeout is None:
            timeout = self.process_timeout
            
        process = None
        try:
            # Start process
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE,
                                     text=True)
            
            # Wait for completion with timeout
            stdout, stderr = process.communicate(timeout=timeout)
            
            return process.returncode, stdout, stderr
            
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg process timed out after {timeout} seconds")
            if process:
                # Try graceful termination first
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    process.kill()
                    process.wait()
            return -1, "", "Process timed out"
            
        except Exception as e:
            logger.error(f"FFmpeg process error: {str(e)}", exc_info=True)
            if process and process.poll() is None:
                process.kill()
                process.wait()
            return -1, "", str(e)
            
        finally:
            # Ensure process is cleaned up
            if process and process.poll() is None:
                process.kill()
                process.wait()
    
    def create_shadowing_video(self, media_path: str, ass_path: str, output_path: str, 
                              start_time: float = None, end_time: float = None,
                              padding_before: float = 0.5, padding_after: float = 0.5,
                              subtitle_data: Dict = None, save_individual_clips: bool = True) -> bool:
        """Create shadowing video with pattern: 2x no subtitle, 2x korean with note, 2x both subtitles
        
        Args:
            save_individual_clips: If True, save individual clips in a subfolder
        """
        
        # Validate input files
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")
        if not os.path.exists(ass_path):
            raise FileNotFoundError(f"ASS file not found: {ass_path}")
        
        # Calculate padded times if specified
        if start_time is not None and end_time is not None:
            padded_start = max(0, start_time - padding_before)
            padded_end = end_time + padding_after
            duration = padded_end - padded_start
            
            # Create time-adjusted ASS file for this clip
            from ass_generator import ASSGenerator
            
            temp_ass_file = tempfile.NamedTemporaryFile(suffix='.ass', delete=False)
            temp_ass_file.close()
            
            try:
                # Use provided subtitle data or load from file
                if subtitle_data:
                    matching_subtitle = subtitle_data
                else:
                    # Load original translated subtitles to find matching subtitle
                    translated_json = ass_path.replace('.ass', '_translated.json')
                    if os.path.exists(translated_json):
                        with open(translated_json, 'r', encoding='utf-8') as f:
                            subtitles_data = json.load(f)
                        
                        # Find the subtitle that matches this time range
                        # Use the original time range (without padding) to find the correct subtitle
                        matching_subtitle = None
                        for sub in subtitles_data:
                            # Check if this subtitle's center point falls within our original time range
                            sub_center = (sub['start_time'] + sub['end_time']) / 2
                            if start_time <= sub_center <= end_time:
                                matching_subtitle = sub
                                break
                
                if matching_subtitle:
                    # Generate ASS file with only this subtitle, adjusted for clip timing
                    ass_generator = ASSGenerator()
                    clip_subtitle = matching_subtitle.copy()
                    # Adjust timing relative to clip start (keep original duration)
                    original_duration = clip_subtitle['end_time'] - clip_subtitle['start_time']
                    clip_subtitle['start_time'] = clip_subtitle['start_time'] - padded_start
                    clip_subtitle['end_time'] = clip_subtitle['start_time'] + original_duration
                    
                    # Generate both subtitles ASS file
                    ass_generator.generate_ass([clip_subtitle], temp_ass_file.name)
                    
                    # Generate Korean-with-note ASS file
                    temp_korean_ass_file = tempfile.NamedTemporaryFile(suffix='_korean_note.ass', delete=False)
                    temp_korean_ass_file.close()
                    korean_note_subtitle = clip_subtitle.copy()
                    # For Type 2, use blank text with Korean subtitle
                    if subtitle_data and 'clipping_type' in subtitle_data and subtitle_data['clipping_type'] == 2:
                        print(f"[DEBUG] Type 2 detected - Creating blank+Korean subtitle")
                        print(f"[DEBUG] Korean text: {korean_note_subtitle.get('kor', 'NO KOREAN')}")
                        # Use pre-generated blank text if available
                        if 'text_eng_blank' in subtitle_data and subtitle_data['text_eng_blank']:
                            korean_note_subtitle['eng'] = subtitle_data['text_eng_blank']
                            korean_note_subtitle['english'] = subtitle_data['text_eng_blank']
                        else:
                            korean_note_subtitle['eng'] = ''
                            korean_note_subtitle['english'] = ''
                        # Keep Korean text for Type 2 - ensure it's actually there
                        if 'korean' in subtitle_data:
                            korean_note_subtitle['kor'] = subtitle_data['korean']
                            korean_note_subtitle['korean'] = subtitle_data['korean']
                        elif 'kor' in subtitle_data:
                            korean_note_subtitle['kor'] = subtitle_data['kor']
                            korean_note_subtitle['korean'] = subtitle_data['kor']
                    else:
                        # Type 1: Remove English text completely, keep Korean
                        korean_note_subtitle['eng'] = ''
                        korean_note_subtitle['english'] = ''
                    # Note will be displayed if present in the subtitle data
                    print(f"[DEBUG] Generating Korean ASS with: eng='{korean_note_subtitle.get('eng', '')}', kor='{korean_note_subtitle.get('kor', '')}', note='{korean_note_subtitle.get('note', '')}'")
                    ass_generator.generate_ass([korean_note_subtitle], temp_korean_ass_file.name)
                    
                    # Store both ASS file paths
                    ass_path = temp_ass_file.name
                    korean_ass_path = temp_korean_ass_file.name
                else:
                    print(f"Warning: No matching subtitle found for time range {padded_start}-{padded_end}")
                    # Create empty ASS file to avoid subtitle accumulation
                    ass_generator = ASSGenerator()
                    ass_generator.generate_ass([], temp_ass_file.name)
                    ass_path = temp_ass_file.name
                    
            except Exception as e:
                print(f"Warning: Could not create time-adjusted ASS file: {e}")
                # Continue with original ASS file
                pass
        else:
            padded_start = None
            padded_end = None
            duration = None
            korean_ass_path = None
        
        temp_clips = []
        temp_ass_file = None
        temp_korean_ass_file = None
        
        # Create clips subfolder if saving individual clips
        if save_individual_clips:
            # Create main clips directory at the same level as output
            clips_base_dir = Path(output_path).parent / "individual_clips"
            clips_base_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract clip number from output path (e.g., shadowing_0001.mp4 -> 0001)
            clip_number = Path(output_path).stem.split('_')[-1] if '_' in Path(output_path).stem else '0000'
            clip_index = 1
            
            # 1. Create no-subtitle clips
            for i in range(self.pattern["no_subtitle"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                if not self._encode_clip(media_path, temp_clips[-1], 
                                       padded_start, duration, 
                                       subtitle_file=None):
                    raise Exception(f"Failed to create no-subtitle clip {i+1}")
                
                # Save individual clip if requested
                if save_individual_clips:
                    nosub_dir = clips_base_dir / "1_nosub"
                    nosub_dir.mkdir(exist_ok=True)
                    clip_filename = nosub_dir / f"clip_{clip_number}_{i+1}.mp4"
                    import shutil
                    shutil.copy2(temp_clips[-1], str(clip_filename))
                    print(f"Saved: {clip_filename.relative_to(clips_base_dir)}")
                
                print(f"Created no-subtitle clip {i+1}/{self.pattern['no_subtitle']}")
                clip_index += 1
            
            # 2. Create korean-with-note subtitle clips
            for i in range(self.pattern["korean_with_note"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                # Use korean-with-note ASS if available, otherwise use full ASS
                korean_subtitle_file = korean_ass_path if 'korean_ass_path' in locals() and korean_ass_path else ass_path
                
                if not self._encode_clip(media_path, temp_clips[-1], 
                                       padded_start, duration, 
                                       subtitle_file=korean_subtitle_file):
                    raise Exception(f"Failed to create korean-with-note subtitle clip {i+1}")
                
                # Save individual clip if requested
                if save_individual_clips:
                    korean_dir = clips_base_dir / "2_korean_note"
                    korean_dir.mkdir(exist_ok=True)
                    clip_filename = korean_dir / f"clip_{clip_number}_{i+1}.mp4"
                    import shutil
                    shutil.copy2(temp_clips[-1], str(clip_filename))
                    print(f"Saved: {clip_filename.relative_to(clips_base_dir)}")
                
                print(f"Created korean-with-note subtitle clip {i+1}/{self.pattern['korean_with_note']}")
                clip_index += 1
            
            # 3. Create both subtitle clips
            for i in range(self.pattern["both_subtitle"]):
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clips.append(temp_file.name)
                temp_file.close()
                
                if not self._encode_clip(media_path, temp_clips[-1], 
                                       padded_start, duration, 
                                       subtitle_file=ass_path):
                    raise Exception(f"Failed to create both subtitle clip {i+1}")
                
                # Save individual clip if requested
                if save_individual_clips:
                    both_dir = clips_base_dir / "3_both"
                    both_dir.mkdir(exist_ok=True)
                    clip_filename = both_dir / f"clip_{clip_number}_{i+1}.mp4"
                    import shutil
                    shutil.copy2(temp_clips[-1], str(clip_filename))
                    print(f"Saved: {clip_filename.relative_to(clips_base_dir)}")
                
                print(f"Created both subtitle clip {i+1}/{self.pattern['both_subtitle']}")
                clip_index += 1
            
            # 4. Concatenate all clips with 1.5s freeze frame gaps
            if not self._concatenate_clips(temp_clips, output_path, gap_duration=1.5):
                raise Exception("Failed to concatenate clips")
            
            print(f"Successfully created shadowing video: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error creating shadowing video: {str(e)}")
            return False
            
        finally:
            # Clean up temporary files
            for temp_clip in temp_clips:
                if os.path.exists(temp_clip):
                    os.unlink(temp_clip)
            
            # Clean up temporary ASS file if created
            if temp_ass_file and os.path.exists(temp_ass_file):
                os.unlink(temp_ass_file)
            
            # Clean up temporary Korean ASS file if created
            if 'temp_korean_ass_file' in locals() and temp_korean_ass_file and os.path.exists(temp_korean_ass_file.name):
                os.unlink(temp_korean_ass_file.name)
    
    def _encode_clip(self, input_path: str, output_path: str, 
                    start_time: Optional[float], duration: Optional[float], 
                    subtitle_file: Optional[str]) -> bool:
        """Encode a single clip with or without subtitles"""
        
        # Choose encoding settings
        settings = self.encoding_settings["with_subtitle" if subtitle_file else "no_subtitle"]
        
        # Build FFmpeg command
        cmd = ['ffmpeg', '-y']  # -y for overwrite
        
        # Input file with seeking if specified
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        # Duration if specified
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # Video filter for subtitles and scaling
        video_filter = f"scale={settings['width']}:{settings['height']}"
        if subtitle_file:
            # Use absolute path and escape special characters for FFmpeg filter
            abs_path = os.path.abspath(subtitle_file)
            # Properly escape for FFmpeg ass filter:
            # Replace backslash with forward slash (Windows compatibility)
            # Escape colons, brackets, and other special characters
            escaped_path = abs_path.replace('\\', '/').replace(':', '\\:')
            escaped_path = escaped_path.replace('[', '\\[').replace(']', '\\]')
            escaped_path = escaped_path.replace(',', '\\,').replace("'", "\\'")
            video_filter = f"scale={settings['width']}:{settings['height']},ass={escaped_path}"
        
        cmd.extend(['-vf', video_filter])
        
        # Video encoding settings
        cmd.extend([
            '-c:v', settings['video_codec'],
            '-preset', settings['preset'],
            '-crf', settings['crf'],
            '-profile:v', settings['profile'],
            '-level', settings['level'],
            '-pix_fmt', settings['pix_fmt']
        ])
        
        # 추가 품질 옵션
        if 'tune' in settings:
            cmd.extend(['-tune', settings['tune']])
        if 'x264opts' in settings:
            cmd.extend(['-x264opts', settings['x264opts']])
        
        # Audio encoding settings
        cmd.extend([
            '-c:a', settings['audio_codec'],
            '-b:a', settings['audio_bitrate']
        ])
        
        # Output settings
        cmd.extend([
            '-movflags', '+faststart',
            output_path
        ])
        
        # Execute command with timeout
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            print(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _concatenate_clips(self, clip_paths: List[str], output_path: str, gap_duration: float = 0.5) -> bool:
        """Concatenate multiple video clips with gaps between them"""
        
        print(f"[DEBUG] _concatenate_clips called with {len(clip_paths)} clips, gap_duration={gap_duration}")
        
        if not clip_paths:
            return False
        
        # If only one clip, just copy it
        if len(clip_paths) == 1:
            import shutil
            shutil.copy2(clip_paths[0], output_path)
            return True
        
        # If no gap needed, use simple concat
        if gap_duration <= 0.0:
            # Create concat file without gaps
            concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            
            try:
                # Write file paths to concat file
                for clip_path in clip_paths:
                    # Escape path for concat demuxer
                    escaped_path = clip_path.replace('\\', '/').replace("'", "'\\''")
                    concat_file.write(f"file '{escaped_path}'\n")
                
                concat_file.close()
                
                # Build FFmpeg concat command
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file.name,
                    '-c', 'copy',
                    output_path
                ]
                
                # Execute command
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"FFmpeg concat error: {result.stderr}")
                    return False
                
                return True
                
            finally:
                # Clean up concat file
                if os.path.exists(concat_file.name):
                    os.unlink(concat_file.name)
        
        # Create temp files list for cleanup
        temp_freeze_files = []
        
        try:
            # Get video info from first clip
            probe_cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', clip_paths[0]
            ]
            
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if probe_result.returncode != 0:
                print(f"Failed to probe video: {probe_result.stderr}")
                return False
            
            import json
            video_info = json.loads(probe_result.stdout)
            video_stream = next(s for s in video_info['streams'] if s['codec_type'] == 'video')
            width = video_stream['width']
            height = video_stream['height']
            
            # Create concat file
            concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            
            # Write file paths to concat file with freeze frame gaps
            for i, clip_path in enumerate(clip_paths):
                # Escape path for concat demuxer
                escaped_path = clip_path.replace('\\', '/').replace("'", "'\\''")
                concat_file.write(f"file '{escaped_path}'\n")
                
                # Add freeze frame gap after each clip (including the last one)
                if True:  # Always add gap, even after the last clip
                    # Create freeze frame from current clip's last frame
                    freeze_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    freeze_file.close()
                    temp_freeze_files.append(freeze_file.name)
                    
                    # Enhanced freeze frame creation with better compatibility
                    # Step 1: Extract last frame as image
                    last_frame_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    last_frame_file.close()
                    temp_freeze_files.append(last_frame_file.name)
                    
                    extract_cmd = [
                        'ffmpeg', '-y',
                        '-sseof', '-0.1',  # Get from 0.1 second before end
                        '-i', clip_path,
                        '-vframes', '1',  # Extract single frame
                        '-f', 'image2',
                        last_frame_file.name
                    ]
                    
                    extract_result = subprocess.run(extract_cmd, capture_output=True, text=True)
                    
                    if extract_result.returncode == 0:
                        # Step 2: Create silent WAV file
                        silence_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        silence_wav.close()
                        temp_freeze_files.append(silence_wav.name)
                        
                        silence_cmd = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi',
                            '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-t', str(gap_duration),
                            '-acodec', 'pcm_s16le',
                            '-ar', '44100',
                            '-ac', '2',
                            silence_wav.name
                        ]
                        
                        silence_result = subprocess.run(silence_cmd, capture_output=True, text=True)
                        
                        # Step 3: Create video from still image with silent WAV
                        freeze_cmd = [
                            'ffmpeg', '-y',
                            '-loop', '1',
                            '-i', last_frame_file.name,
                            '-i', silence_wav.name,
                            '-t', str(gap_duration),
                            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                            '-c:v', 'libx264',
                            '-preset', 'veryfast',
                            '-crf', '18',
                            '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-ar', '44100',
                            '-ac', '2',
                            '-shortest',
                            freeze_file.name
                        ]
                    else:
                        # Fallback: use direct method
                        freeze_cmd = [
                            'ffmpeg', '-y',
                            '-sseof', '-0.1',
                            '-i', clip_path,
                            '-t', str(gap_duration),
                            '-vf', f'select=\'eq(n\\,0)\',scale={width}:{height},setpts=N/TB',
                            '-af', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-c:v', 'libx264',
                            '-preset', 'veryfast',
                            '-crf', '18',
                            '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-ar', '44100',
                            '-ac', '2',
                            freeze_file.name
                        ]
                    
                    print(f"[DEBUG] Creating freeze frame {i+1} with duration {gap_duration}s")
                    freeze_result = subprocess.run(freeze_cmd, capture_output=True, text=True)
                    
                    if freeze_result.returncode == 0:
                        freeze_escaped = freeze_file.name.replace('\\', '/').replace("'", "'\\''")
                        concat_file.write(f"file '{freeze_escaped}'\n")
                        print(f"[DEBUG] Successfully created freeze frame: {freeze_file.name}")
                    else:
                        print(f"[ERROR] Freeze frame creation failed: {freeze_result.stderr}")
                        print(f"[ERROR] Command was: {' '.join(freeze_cmd)}")
                        
                        # Try one more time with a simpler method
                        # Create silent WAV first
                        simple_silence_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        simple_silence_wav.close()
                        temp_freeze_files.append(simple_silence_wav.name)
                        
                        simple_silence_cmd = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi',
                            '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-t', str(gap_duration),
                            '-acodec', 'pcm_s16le',
                            '-ar', '44100',
                            '-ac', '2',
                            simple_silence_wav.name
                        ]
                        subprocess.run(simple_silence_cmd, capture_output=True, text=True)
                        
                        simple_freeze_cmd = [
                            'ffmpeg', '-y',
                            '-i', clip_path,
                            '-i', simple_silence_wav.name,
                            '-ss', '0',  # Take first frame instead
                            '-t', str(gap_duration),
                            '-vf', f'select=\'eq(n\\,0)\',scale={width}:{height}',
                            '-map', '0:v',
                            '-map', '1:a',
                            '-c:v', 'libx264',
                            '-preset', 'veryfast',
                            '-crf', '18',
                            '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            freeze_file.name
                        ]
                        
                        simple_result = subprocess.run(simple_freeze_cmd, capture_output=True, text=True)
                        if simple_result.returncode == 0:
                            freeze_escaped = freeze_file.name.replace('\\', '/').replace("'", "'\\''")
                            concat_file.write(f"file '{freeze_escaped}'\n")
                            print(f"[DEBUG] Successfully created freeze frame with simple method")
                        else:
                            print(f"[ERROR] All freeze frame methods failed, skipping gap")
            
            concat_file.close()
            
            # Build FFmpeg concat command with audio re-encoding
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                '-af', 'aresample=async=1:min_hard_comp=0.100000:first_pts=0',
                output_path
            ]
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"FFmpeg concat error: {result.stderr}")
                return False
            
            return True
            
        finally:
            # Clean up temporary files
            for freeze_file in temp_freeze_files:
                if os.path.exists(freeze_file):
                    os.unlink(freeze_file)
            if 'concat_file' in locals() and os.path.exists(concat_file.name):
                os.unlink(concat_file.name)
    
    def create_shadowing_video_efficient(self, media_path: str, ass_path: str, output_path: str, 
                                        start_time: float = None, end_time: float = None,
                                        padding_before: float = 0.5, padding_after: float = 0.5) -> bool:
        """Create shadowing video efficiently using FFmpeg concat filter"""
        
        # Validate input files
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")
        if not os.path.exists(ass_path):
            raise FileNotFoundError(f"ASS file not found: {ass_path}")
        
        # Calculate padded times if specified
        if start_time is not None and end_time is not None:
            padded_start = max(0, start_time - padding_before)
            padded_end = end_time + padding_after
            duration = padded_end - padded_start
            
            # Create time-adjusted ASS file for this clip
            temp_ass_file = tempfile.NamedTemporaryFile(suffix='.ass', delete=False)
            temp_ass_file.close()
            
            try:
                # Load original translated subtitles to find matching subtitle
                translated_json = ass_path.replace('.ass', '_translated.json')
                if os.path.exists(translated_json):
                    with open(translated_json, 'r', encoding='utf-8') as f:
                        subtitles_data = json.load(f)
                    
                    # Find the subtitle that matches this time range
                    matching_subtitle = None
                    for sub in subtitles_data:
                        if (sub['start_time'] <= padded_end and sub['end_time'] >= padded_start):
                            matching_subtitle = sub
                            break
                    
                    if matching_subtitle:
                        # Generate ASS file with only this subtitle
                        from ass_generator import ASSGenerator
                        ass_generator = ASSGenerator()
                        clip_subtitle = matching_subtitle.copy()
                        clip_subtitle['start_time'] = 0.0
                        clip_subtitle['end_time'] = duration
                        
                        ass_generator.generate_ass([clip_subtitle], temp_ass_file.name)
                        ass_path = temp_ass_file.name
                    else:
                        # Create empty ASS file
                        from ass_generator import ASSGenerator
                        ass_generator = ASSGenerator()
                        ass_generator.generate_ass([], temp_ass_file.name)
                        ass_path = temp_ass_file.name
                        
            except Exception as e:
                print(f"Warning: Could not create time-adjusted ASS file: {e}")
                pass
        else:
            padded_start = None
            duration = None
        
        try:
            # Build FFmpeg command with concat filter
            cmd = ['ffmpeg', '-y']
            
            # Input file with seeking if specified
            if padded_start is not None:
                cmd.extend(['-ss', str(padded_start)])
            
            cmd.extend(['-i', media_path])
            
            # Duration if specified
            if duration is not None:
                cmd.extend(['-t', str(duration)])
            
            # Settings
            settings = self.encoding_settings["with_subtitle"]
            
            # Create complex filter for shadowing pattern
            # 1x no subtitle + 3x with subtitle + gaps
            # Escape ASS path for filter_complex
            ass_escaped = os.path.abspath(ass_path).replace(':', '\\:').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
            
            filter_complex = f"""
            [0:v]scale={settings['width']}:{settings['height']}[v_scaled];
            [v_scaled]ass={ass_escaped}[v_sub];
            [v_scaled][v_sub][v_sub][v_sub]concat=n=4:v=1:a=0[v_out];
            [0:a][0:a][0:a][0:a]concat=n=4:v=0:a=1[a_out];
            color=black:size={settings['width']}x{settings['height']}:duration=0.5[gap];
            [v_out][gap][gap][gap]concat=n=4:v=1:a=0[v_final];
            [a_out]apad=pad_dur=1.5[a_final]
            """
            
            cmd.extend(['-filter_complex', filter_complex.strip()])
            cmd.extend(['-map', '[v_final]', '-map', '[a_final]'])
            
            # Encoding settings
            cmd.extend([
                '-c:v', settings['video_codec'],
                '-preset', settings['preset'],
                '-crf', settings['crf'],
                '-profile:v', settings['profile'],
                '-level', settings['level'],
                '-pix_fmt', settings['pix_fmt'],
                '-c:a', settings['audio_codec'],
                '-b:a', settings['audio_bitrate'],
                '-movflags', '+faststart',
                output_path
            ])
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return False
            
            print(f"Successfully created shadowing video: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error creating shadowing video: {str(e)}")
            return False
            
        finally:
            # Clean up temporary ASS file if created
            if 'temp_ass_file' in locals() and os.path.exists(temp_ass_file.name):
                os.unlink(temp_ass_file.name)

    def process_full_video(self, media_path: str, subtitles: List[Dict], 
                          ass_path: str, output_dir: str, 
                          padding_before: float = 0.5, padding_after: float = 0.5) -> List[str]:
        """Process full video into multiple shadowing clips"""
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        created_files = []
        
        for i, sub in enumerate(subtitles):
            # Use start time for filename (format: 0015.5.mp4)
            # Format: 4-digit seconds + decimal point + 1 decimal place (truncated, not rounded)
            import math
            truncated_time = math.floor(sub['start_time'] * 10) / 10
            filename = f"{truncated_time:.1f}"
            output_file = output_dir / f"{filename.zfill(7)}.mp4"  # 5자리 + 소수점 + 1자리 = 7
            
            success = self.create_shadowing_video(
                media_path=media_path,
                ass_path=ass_path,
                output_path=str(output_file),
                start_time=sub['start_time'],
                end_time=sub['end_time'],
                padding_before=padding_before,
                padding_after=padding_after,
                subtitle_data=sub  # 직접 자막 데이터 전달
            )
            
            if success:
                created_files.append(str(output_file))
                print(f"Progress: {i+1}/{len(subtitles)} clips created")
            else:
                print(f"Warning: Failed to create clip {i+1}")
        
        return created_files


if __name__ == "__main__":
    # Test the encoder
    encoder = VideoEncoder()
    
    # Test with sample files
    media_file = "/home/kang/dev/youtube_maker/shadowing_maker_cli/media/Emily.in.Paris.S01E01.1080p.WEB.H264-CAKES.mkv"
    ass_file = "/home/kang/dev/youtube_maker/shadowing_maker_cli/media/Emily.in.Paris.S01E01.1080p.WEB.H264-CAKES.ass"
    
    if os.path.exists(media_file) and os.path.exists(ass_file):
        # Test single clip
        output_file = "/home/kang/dev/youtube_maker/shadowing_maker_cli/media/test_shadowing.mp4"
        
        success = encoder.create_shadowing_video(
            media_path=media_file,
            ass_path=ass_file,
            output_path=output_file,
            start_time=30.0,  # Start at 30 seconds
            end_time=40.0     # End at 40 seconds
        )
        
        if success:
            print(f"Test shadowing video created: {output_file}")
        else:
            print("Failed to create test shadowing video")