#!/usr/bin/env python3
"""
간단한 자막 테스트 스크립트
"""
import os
import subprocess
import tempfile
from ass_generator import ASSGenerator

# 1. 테스트 비디오 생성 (5초 검은 화면)
test_video = "/tmp/test_video.mp4"
subprocess.run([
    "ffmpeg", "-f", "lavfi", "-i", "color=black:1920x1080:d=5",
    "-c:v", "libx264", "-y", test_video
], capture_output=True)

print(f"테스트 비디오 생성됨: {test_video}")

# 2. ASS 자막 생성
ass_gen = ASSGenerator()
subtitle_data = {
    'start_time': 1.0,
    'end_time': 4.0,
    'eng': 'Hello World',
    'kor': '안녕하세요',
    'english': 'Hello World',
    'korean': '안녕하세요'
}

with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as ass_file:
    ass_gen.generate_ass([subtitle_data], ass_file.name)
    print(f"ASS 파일 생성됨: {ass_file.name}")
    
    # ASS 파일 내용 확인
    with open(ass_file.name, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'Hello World' in content and '안녕하세요' in content:
            print("✓ ASS 파일에 자막이 포함되어 있음")
        else:
            print("✗ ASS 파일에 자막이 없음!")
            print("ASS 내용:")
            print(content)

# 3. FFmpeg로 자막 삽입
output_video = "/tmp/test_subtitle_output.mp4"
font_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'font'))

cmd = [
    "ffmpeg", "-i", test_video,
    "-vf", f"ass={ass_file.name}:fontsdir={font_dir}",
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-y", output_video
]

print("\nFFmpeg 명령어:")
print(' '.join(cmd))

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    print(f"\n✓ 자막이 삽입된 비디오 생성됨: {output_video}")
    print("FFprobe로 확인:")
    
    # 생성된 비디오 확인
    probe_cmd = ["ffprobe", "-v", "error", "-show_streams", output_video]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    
    if "subtitle" in probe_result.stdout or os.path.exists(output_video):
        print("비디오가 성공적으로 생성되었습니다.")
        print(f"파일 크기: {os.path.getsize(output_video)} bytes")
else:
    print(f"\n✗ FFmpeg 실패: {result.returncode}")
    print("에러 출력:")
    print(result.stderr)

# 정리
os.unlink(ass_file.name)
print(f"\n임시 파일 정리됨")