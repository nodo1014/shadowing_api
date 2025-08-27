#!/usr/bin/env python3
"""
Simple review clip test without TTS
"""

import subprocess
import tempfile

def create_simple_review():
    """TTS 없이 간단한 리뷰 클립 생성"""
    
    clips_data = [
        {'text_eng': 'Hello world', 'text_kor': '안녕 세상'}
    ]
    
    width, height = 1080, 1920  # 쇼츠
    
    # 각 클립당 3초씩
    clip_duration = 3.0
    
    print("Creating simple review clip without TTS...")
    
    temp_clips = []
    
    # 타이틀 클립 (2초)
    title_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    title_file.close()
    temp_clips.append(title_file.name)
    
    cmd_title = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'color=c=black:s={width}x{height}:d=2',
        '-vf', "drawtext=text='스피드 복습':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=100:fontcolor=#FFD700:x=(w-text_w)/2:y=(h-text_h)/2",
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '20',
        title_file.name
    ]
    
    print("Creating title clip...")
    result = subprocess.run(cmd_title, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Title clip failed: {result.stderr}")
        return False
    
    # 텍스트 클립들
    for idx, clip_data in enumerate(clips_data):
        clip_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        clip_file.close()
        temp_clips.append(clip_file.name)
        
        text_kor = clip_data['text_kor'].replace(":", "\\:")
        text_eng = clip_data['text_eng'].replace(":", "\\:")
        
        cmd_clip = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s={width}x{height}:d={clip_duration}',
            '-vf', (
                f"drawtext=text='{text_kor}':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=60:"
                f"fontcolor=white:x=(w-text_w)/2:y={(height//2)-80},"
                f"drawtext=text='{text_eng}':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=50:"
                f"fontcolor=#FFD700:x=(w-text_w)/2:y={(height//2)+20}"
            ),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '20',
            clip_file.name
        ]
        
        print(f"Creating text clip {idx+1}...")
        result = subprocess.run(cmd_clip, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Text clip {idx+1} failed: {result.stderr}")
            return False
    
    # concat 파일 생성
    concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    for clip in temp_clips:
        concat_file.write(f"file '{clip}'\n")
    concat_file.close()
    
    # 최종 합성
    output_path = "/home/kang/dev_amd/shadowing_maker_xls/simple_review_test.mp4"
    cmd_final = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file.name,
        '-c:v', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    
    print("Combining clips...")
    result = subprocess.run(cmd_final, capture_output=True, text=True)
    
    # 정리
    import os
    for temp_file in temp_clips + [concat_file.name]:
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    if result.returncode == 0:
        print(f"✓ Simple review clip created: {output_path}")
        # 파일 크기 확인
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  File size: {size_mb:.2f} MB")
        return True
    else:
        print(f"✗ Final combine failed: {result.stderr}")
        return False

if __name__ == "__main__":
    create_simple_review()