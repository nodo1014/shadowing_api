#!/usr/bin/env python3
"""
Test script to reproduce and fix Template 1 video freeze issue
"""
import json
import tempfile
import subprocess
import os
from pathlib import Path

def test_multiple_clip_encoding():
    """Test encoding the same video segment multiple times"""
    
    # Test video path
    test_video = "/mnt/qnap/media_eng/indexed_media/animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    if not os.path.exists(test_video):
        print(f"Test video not found: {test_video}")
        return
    
    # Create 5 clips from the same segment (10.5s - 15.5s)
    start_time = 10.5
    end_time = 15.5
    duration = end_time - start_time
    
    temp_clips = []
    
    for i in range(5):
        temp_file = tempfile.NamedTemporaryFile(suffix=f'_clip{i+1}.mp4', delete=False)
        temp_clips.append(temp_file.name)
        temp_file.close()
        
        # Basic encoding command
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', test_video,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            temp_clips[-1]
        ]
        
        print(f"Creating clip {i+1}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error creating clip {i+1}: {result.stderr}")
            return
        else:
            print(f"Successfully created clip {i+1}: {temp_clips[-1]}")
    
    # Check if all clips are identical
    print("\nChecking clip properties...")
    for i, clip in enumerate(temp_clips):
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', clip]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
            if video_stream:
                print(f"Clip {i+1}: {video_stream.get('width')}x{video_stream.get('height')}, "
                      f"duration: {video_stream.get('duration', 'N/A')}s, "
                      f"nb_frames: {video_stream.get('nb_frames', 'N/A')}")
    
    # Create concat list
    concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    for clip in temp_clips:
        escaped_path = clip.replace('\\', '/').replace("'", "'\\''")
        concat_file.write(f"file '{escaped_path}'\n")
    concat_file.close()
    
    # Concatenate clips
    output_file = "/home/kang/dev_amd/shadowing_maker_xls/output/test_template1_concat.mp4"
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file.name,
        '-c', 'copy',
        output_file
    ]
    
    print(f"\nConcatenating clips...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error concatenating: {result.stderr}")
    else:
        print(f"Successfully created concatenated video: {output_file}")
        print("Please check if all 5 segments show video movement or if some are frozen.")
    
    # Cleanup
    os.unlink(concat_file.name)
    for clip in temp_clips:
        if os.path.exists(clip):
            os.unlink(clip)

if __name__ == "__main__":
    test_multiple_clip_encoding()