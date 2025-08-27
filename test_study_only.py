#!/usr/bin/env python3
"""
스터디 클립 생성만 테스트
기존 배치 처리는 제외하고 스터디 클립만 집중
"""

import asyncio
import os
import subprocess
from review_clip_generator import ReviewClipGenerator

async def test_study_clip_only():
    """스터디 클립만 생성하는 간단한 테스트"""
    
    print("🎯 스터디 클립 생성만 테스트합니다...")
    print("=" * 60)
    
    # 테스트 데이터
    clips_data = [
        {
            "text_eng": "You will be Hunters.", 
            "text_kor": "너희는 헌터가 될 거야"
        }
    ]
    
    # 출력 디렉토리 생성
    output_dir = "test_study_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 타이틀 클립만 생성
    print("\n1️⃣ 타이틀 클립 생성 중...")
    title_cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:d=2',
        '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-vf', "drawtext=text='스피드 복습':fontfile='/usr/share/fonts/truetype/nanum/NanumGothic.ttf':fontsize=120:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        '-c:v', 'libx264', '-c:a', 'aac',
        f'{output_dir}/000_title.mp4'
    ]
    
    result = subprocess.run(title_cmd, capture_output=True)
    if result.returncode == 0:
        print("✅ 타이틀 클립 생성 성공")
    else:
        print(f"❌ 타이틀 클립 생성 실패: {result.stderr.decode()}")
        return
    
    # 2. ReviewClipGenerator로 전체 스터디 클립 생성
    print("\n2️⃣ ReviewClipGenerator로 스터디 클립 생성 중...")
    generator = ReviewClipGenerator()
    
    study_output = f"{output_dir}/study_clip_complete.mp4"
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=study_output,
        title="스피드 복습",
        template_number=11
    )
    
    if success:
        print("✅ 스터디 클립 생성 성공")
        
        # 생성된 파일 정보 확인
        print("\n📊 생성된 파일 분석:")
        for file in os.listdir(output_dir):
            if file.endswith('.mp4'):
                filepath = os.path.join(output_dir, file)
                
                # 길이 확인
                duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 
                               'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
                               filepath]
                duration = subprocess.run(duration_cmd, capture_output=True, text=True)
                
                # 스트림 확인
                stream_cmd = ['ffprobe', '-v', 'error', '-show_streams', filepath]
                streams = subprocess.run(stream_cmd, capture_output=True, text=True)
                
                has_video = 'codec_type=video' in streams.stdout
                has_audio = 'codec_type=audio' in streams.stdout
                
                print(f"\n📁 {file}:")
                print(f"   Duration: {duration.stdout.strip()}s")
                print(f"   Video: {'✅' if has_video else '❌'}")
                print(f"   Audio: {'✅' if has_audio else '❌'}")
                print(f"   Size: {os.path.getsize(filepath) / 1024:.1f} KB")
    else:
        print("❌ 스터디 클립 생성 실패")
    
    print("\n" + "=" * 60)
    print("✅ 스터디 클립만 테스트 완료!")
    print(f"📂 결과 디렉토리: {output_dir}/")

if __name__ == "__main__":
    # 스터디 클립만 테스트
    asyncio.run(test_study_clip_only())
    
    print("\n💡 다음 단계:")
    print("1. 생성된 스터디 클립이 정상적인지 확인")
    print("2. 기존 템플릿 클립과 형식이 동일한지 확인")
    print("3. 두 클립을 단순 concat으로 병합 테스트")