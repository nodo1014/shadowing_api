#!/usr/bin/env python3
"""
무음 + TTS를 하나의 오디오로 연결
"""
import subprocess
import asyncio
from edge_tts_util import EdgeTTSGenerator

async def generate_tts_first():
    """Aria 음성으로 TTS 생성"""
    tts_gen = EdgeTTSGenerator(voice='en-US-AriaNeural', rate='-10%')
    await tts_gen.generate_tts_async('You will be Hunters.', 'test_tts_output.mp3')
    print("✅ TTS 생성 완료 (Aria 음성, 속도 -10%)")

# TTS 생성
asyncio.run(generate_tts_first())

# 1. 2초 무음 생성
silence_cmd = [
    'ffmpeg', '-y',
    '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
    '-t', '2',
    'silence_2s.wav'
]
subprocess.run(silence_cmd)

# 2. 무음 + TTS 연결
concat_audio_cmd = [
    'ffmpeg', '-y',
    '-i', 'silence_2s.wav',
    '-i', 'test_tts_output.mp3',
    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[outa]',
    '-map', '[outa]',
    'combined_audio.mp3'
]
subprocess.run(concat_audio_cmd)

# 3. 비디오 생성 (타이틀 2초 + 문장 2.4초)
video_cmd = [
    'ffmpeg', '-y',
    '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:d=4.4',
    '-i', 'combined_audio.mp3',
    '-vf', (
        # 0-2초: 타이틀
        "drawtext=text='스피드 복습':fontsize=120:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,2)',"
        # 2-4.4초: 문장
        "drawtext=text='너희는 헌터가 될 거야':fontsize=80:fontcolor=white:x=(w-text_w)/2:y=h/2-100:enable='between(t,2,4.4)',"
        "drawtext=text='You will be Hunters.':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=h/2:enable='between(t,2,4.4)'"
    ),
    '-c:v', 'libx264', '-c:a', 'aac',
    '-shortest',
    'study_clip_combined.mp4'
]
result = subprocess.run(video_cmd)

if result.returncode == 0:
    print("✅ 생성 성공: study_clip_combined.mp4")
    
    # 오디오 확인
    print("\n오디오 분석:")
    subprocess.run(['ffmpeg', '-i', 'study_clip_combined.mp4', '-af', 'volumedetect', '-f', 'null', '-'], 
                   stderr=subprocess.PIPE)