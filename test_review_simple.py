#!/usr/bin/env python3
"""
Simple test for review clip generation
"""

import subprocess
import tempfile
import os

def create_minimal_review():
    """최소한의 리뷰 클립 생성"""
    
    width, height = 1080, 1920
    
    # 타이틀 클립 (2초, 검은 화면)
    title_clip = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    title_clip.close()
    
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:d=2',
        '-c:v', 'libx264', '-preset', 'fast',
        title_clip.name
    ]
    
    print("Creating title clip...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
        
    # 텍스트 클립 (3초)
    text_clip = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    text_clip.close()
    
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:d=3',
        '-vf', "drawtext=text='Test Review':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        '-c:v', 'libx264', '-preset', 'fast',
        text_clip.name
    ]
    
    print("Creating text clip...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    
    # concat
    concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    concat_file.write(f"file '{title_clip.name}'\n")
    concat_file.write(f"file '{text_clip.name}'\n")
    concat_file.close()
    
    output_path = "test_minimal_review.mp4"
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', concat_file.name,
        '-c', 'copy',
        output_path
    ]
    
    print("Concatenating clips...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Cleanup
    for f in [title_clip.name, text_clip.name, concat_file.name]:
        if os.path.exists(f):
            os.unlink(f)
    
    if result.returncode == 0:
        print(f"✓ Success! Created: {output_path}")
        return True
    else:
        print(f"✗ Failed: {result.stderr}")
        return False

if __name__ == "__main__":
    create_minimal_review()