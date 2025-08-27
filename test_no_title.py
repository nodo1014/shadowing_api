#!/usr/bin/env python3
"""
타이틀 없이 TTS만으로 스터디 클립 생성
"""
import subprocess
import tempfile

# TTS 있는지 확인
tts_file = "test_tts_output.mp3"

# TTS + 자막으로 바로 클립 생성
output = "study_clip_no_title.mp4"

cmd = [
    'ffmpeg', '-y',
    '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:d=2.4',  # TTS 길이만큼
    '-i', tts_file,
    '-vf', "drawtext=text='너희는 헌터가 될 거야':fontsize=80:fontcolor=white:x=(w-text_w)/2:y=h/2-100,"
           "drawtext=text='You will be Hunters.':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=h/2",
    '-c:v', 'libx264', '-c:a', 'aac',
    '-shortest',
    output
]

result = subprocess.run(cmd)
if result.returncode == 0:
    print(f"✅ 생성 성공: {output}")
    
    # 볼륨 확인
    vol_cmd = ['ffmpeg', '-i', output, '-af', 'volumedetect', '-f', 'null', '-']
    subprocess.run(vol_cmd)
else:
    print("❌ 생성 실패")