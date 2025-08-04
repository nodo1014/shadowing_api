#!/usr/bin/env python3
"""
Test if video clips have actual motion or are frozen
"""
import subprocess
import json
import sys
from pathlib import Path

def check_video_motion(video_path):
    """Check if video has motion by comparing frames"""
    
    # Extract frames at different time points
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', 'select=eq(n\\,1)+eq(n\\,30)+eq(n\\,60)+eq(n\\,90)+eq(n\\,120),metadata=print:file=-',
        '-vsync', '0',
        '-f', 'null', '-'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
    
    # Check for scene changes using FFmpeg's scene detection
    scene_cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', 'select=gt(scene\\,0.1),metadata=print:file=-',
        '-f', 'null', '-'
    ]
    
    scene_result = subprocess.run(scene_cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
    
    # Count scene changes
    scene_changes = scene_result.stdout.count('pts_time')
    
    return scene_changes

def analyze_template1_video(video_path):
    """Analyze Template 1 video for frozen segments"""
    
    print(f"Analyzing video: {video_path}")
    
    # Get video duration and segment info
    probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    
    if probe_result.returncode == 0:
        data = json.loads(probe_result.stdout)
        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        if video_stream:
            duration = float(video_stream.get('duration', 0))
            fps = eval(video_stream.get('r_frame_rate', '24/1'))
            print(f"Video duration: {duration:.2f}s, FPS: {fps}")
    
    # Template 1 has 5 segments with gaps
    # Each segment is ~6 seconds, gap is 1.5 seconds
    segment_times = [
        (0, 6),      # Segment 1: no subtitle
        (7.5, 13.5), # Segment 2: blank
        (15, 21),    # Segment 3: blank+korean
        (22.5, 28.5),# Segment 4: both
        (30, 36)     # Segment 5: no subtitle
    ]
    
    print("\nChecking motion in each segment:")
    for i, (start, end) in enumerate(segment_times, 1):
        # Extract a small clip for each segment
        temp_clip = f"/tmp/segment_{i}.mp4"
        extract_cmd = [
            'ffmpeg', '-y', '-ss', str(start), '-i', video_path,
            '-t', '2', '-c', 'copy', temp_clip
        ]
        subprocess.run(extract_cmd, capture_output=True)
        
        # Check motion in the segment
        scene_changes = check_video_motion(temp_clip)
        
        status = "✓ Motion detected" if scene_changes > 0 else "✗ No motion (frozen)"
        print(f"  Segment {i} ({start}s-{end}s): {status} (scene changes: {scene_changes})")
        
        # Cleanup
        Path(temp_clip).unlink(missing_ok=True)

if __name__ == "__main__":
    # Test the generated Template 1 video
    test_video = "/home/kang/dev_amd/shadowing_maker_xls/output/test_template1_real.mp4"
    
    if Path(test_video).exists():
        analyze_template1_video(test_video)
    else:
        print(f"Video not found: {test_video}")
    
    # Also check individual clips
    print("\n" + "="*50)
    print("Checking individual clips for motion:")
    clip_dir = Path("/home/kang/dev_amd/shadowing_maker_xls/output/individual_clips")
    
    if clip_dir.exists():
        for folder in sorted(clip_dir.iterdir()):
            if folder.is_dir():
                for clip in folder.glob("*.mp4"):
                    scene_changes = check_video_motion(str(clip))
                    status = "✓ Motion" if scene_changes > 0 else "✗ Frozen"
                    print(f"  {folder.name}/{clip.name}: {status} (changes: {scene_changes})")