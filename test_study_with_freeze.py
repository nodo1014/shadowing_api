#!/usr/bin/env python3
"""
스터디 클립에 NotoSans 폰트 적용 및 정지 프레임 추출 테스트
"""
import subprocess
import os
import tempfile

# NotoSans 폰트 경로
FONT_PATHS = [
    "/home/kang/.fonts/NotoSansCJK.ttc",
    "/home/kang/.fonts/NotoSansCJKkr-hinted/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Helvetica.ttc"  # 폴백
]

# 사용 가능한 폰트 찾기
font_file = None
for path in FONT_PATHS:
    if os.path.exists(path):
        font_file = path
        print(f"✅ Using font: {path}")
        break

if not font_file:
    print("❌ NotoSans font not found, using default")
    font_file = "NanumGothic"

# 테스트 비디오 경로
test_video = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"

# 1. 원본에서 정지 프레임 추출 (크롭 적용)
print("\n1️⃣ 정지 프레임 추출 (쇼츠 크롭 적용)...")
freeze_frame_time = 52.5  # 문장 중간 시점

# 쇼츠용 크롭/스케일 필터 (template_1_shorts와 동일: 정사각형 크롭)
crop_filter = "crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"

freeze_cmd = [
    'ffmpeg', '-y',
    '-ss', str(freeze_frame_time),
    '-i', test_video,
    '-frames:v', '1',
    '-vf', crop_filter,
    'freeze_frame.png'
]

result = subprocess.run(freeze_cmd, capture_output=True)
if result.returncode == 0:
    print("✅ 정지 프레임 추출 성공")
else:
    print(f"❌ 정지 프레임 추출 실패: {result.stderr.decode()}")

# 2. 정지 프레임으로 스터디 클립 생성 (NotoSans 폰트 사용)
print("\n2️⃣ NotoSans 폰트로 스터디 클립 생성...")

# TTS 오디오 (이미 생성된 것 사용)
tts_audio = "test_tts_output.mp3" if os.path.exists("test_tts_output.mp3") else None

if tts_audio:
    study_cmd = [
        'ffmpeg', '-y',
        # 정지 프레임을 배경으로 사용
        '-loop', '1', '-i', 'freeze_frame.png',
        # TTS 오디오
        '-i', tts_audio,
        # 비디오 필터 (NotoSans 폰트로 텍스트 오버레이)
        '-vf', (
            f"drawtext=text='너희는 헌터가 될 거야':fontfile='{font_file}':"
            f"fontsize=80:fontcolor=white:borderw=3:bordercolor=black:"
            f"x=(w-text_w)/2:y=h/2-100,"
            f"drawtext=text='You will be Hunters.':fontfile='{font_file}':"
            f"fontsize=60:fontcolor=#FFD700:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y=h/2"
        ),
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '22',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        'study_clip_with_freeze.mp4'
    ]
    
    result = subprocess.run(study_cmd, capture_output=True)
    if result.returncode == 0:
        print("✅ 스터디 클립 생성 성공")
        
        # 생성된 클립 정보 확인
        info_cmd = ['ffprobe', '-v', 'error', '-show_streams', 'study_clip_with_freeze.mp4']
        info = subprocess.run(info_cmd, capture_output=True, text=True)
        
        has_video = 'codec_type=video' in info.stdout
        has_audio = 'codec_type=audio' in info.stdout
        
        print(f"\n📊 생성된 클립 정보:")
        print(f"   Video: {'✅' if has_video else '❌'}")
        print(f"   Audio: {'✅' if has_audio else '❌'}")
        print(f"   Font: {os.path.basename(font_file)}")
        print(f"   Background: 정지 프레임 (크롭 적용)")
        
    else:
        print(f"❌ 스터디 클립 생성 실패: {result.stderr.decode()}")
else:
    print("❌ TTS 오디오 파일이 없습니다")

# 3. 타이틀 클립도 동일한 스타일로 생성
print("\n3️⃣ 타이틀 클립 생성 (동일한 스타일)...")

title_cmd = [
    'ffmpeg', '-y',
    '-loop', '1', '-i', 'freeze_frame.png',
    '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
    '-t', '2',
    '-vf', (
        f"drawtext=text='스피드 복습':fontfile='{font_file}':"
        f"fontsize=120:fontcolor=white:borderw=4:bordercolor=black:"
        f"x=(w-text_w)/2:y=(h-text_h)/2"
    ),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
    '-c:a', 'aac', '-b:a', '192k',
    'title_clip_with_freeze.mp4'
]

subprocess.run(title_cmd)
print("✅ 타이틀 클립 생성 완료")

print("\n✅ 모든 작업 완료!")
print("📁 생성된 파일:")
print("   - freeze_frame.png (크롭된 정지 프레임)")
print("   - study_clip_with_freeze.mp4 (NotoSans 폰트 + 정지 프레임 배경)")
print("   - title_clip_with_freeze.mp4 (타이틀 클립)")