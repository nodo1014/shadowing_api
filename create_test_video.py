#!/usr/bin/env python3
"""
Create a test video for testing the template system
"""

import subprocess
import os

def create_test_video():
    """Create a simple test video using FFmpeg"""
    
    output_path = "media/simple_test.mp4"
    
    # Create a 10-second test video with audio
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', 'testsrc=duration=10:size=1920x1080:rate=30',
        '-f', 'lavfi', 
        '-i', 'sine=frequency=1000:duration=10',
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '128k',
        output_path
    ]
    
    print("Creating test video...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ Test video created: {output_path}")
        return True
    else:
        print(f"✗ Failed to create test video")
        print(f"Error: {result.stderr}")
        return False

if __name__ == "__main__":
    create_test_video()