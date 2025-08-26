#!/usr/bin/env python3
"""
Fixed review clip generation test
개선된 리뷰 클립 생성 테스트
"""

import asyncio
import subprocess
import os
from review_clip_generator import ReviewClipGenerator

async def test_fixed_review():
    """개선된 리뷰 클립 생성 테스트"""
    generator = ReviewClipGenerator()
    
    clips_data = [
        {
            "text_eng": "You will be Hunters.", 
            "text_kor": "너희는 헌터가 될 거야"
        }
    ]
    
    output_path = "test_fixed_output.mp4"
    
    print("🔧 Testing fixed review clip generation...")
    print("=" * 60)
    
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=output_path,
        title="스피드 복습",
        template_number=11  # 쇼츠
    )
    
    if success and os.path.exists(output_path):
        print(f"✅ Review clip created successfully: {output_path}")
        
        # 비디오 정보 확인
        print("\n📊 Video analysis:")
        
        # 스트림 정보
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_streams', output_path],
            capture_output=True, text=True
        )
        
        has_video = False
        has_audio = False
        video_codec = ""
        audio_codec = ""
        
        for line in result.stdout.split('\n'):
            if 'codec_type=video' in line:
                has_video = True
            elif 'codec_type=audio' in line:
                has_audio = True
            elif 'codec_name=' in line and has_video and not video_codec:
                video_codec = line.split('=')[1]
            elif 'codec_name=' in line and has_audio and not audio_codec:
                audio_codec = line.split('=')[1]
        
        print(f"  Video stream: {'✅' if has_video else '❌'} {f'({video_codec})' if video_codec else ''}")
        print(f"  Audio stream: {'✅' if has_audio else '❌'} {f'({audio_codec})' if audio_codec else ''}")
        
        # 비디오 길이
        duration_result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', output_path],
            capture_output=True, text=True
        )
        duration = float(duration_result.stdout.strip())
        print(f"  Duration: {duration:.2f} seconds")
        
        # 파일 크기
        file_size = os.path.getsize(output_path) / 1024
        print(f"  File size: {file_size:.1f} KB")
        
        if not has_audio:
            print("\n⚠️  WARNING: No audio stream found in output!")
            return False
            
        print("\n✅ All checks passed!")
        return True
        
    else:
        print("❌ Review clip creation failed")
        return False

async def test_multiple_clips():
    """여러 클립 병합 테스트"""
    generator = ReviewClipGenerator()
    
    clips_data = [
        {
            "text_eng": "You will be Hunters.", 
            "text_kor": "너희는 헌터가 될 거야"
        },
        {
            "text_eng": "Demons have always haunted our world.",
            "text_kor": "악마들은 항상 우리 세계를 괴롭혀왔어."
        }
    ]
    
    output_path = "test_multiple_clips.mp4"
    
    print("\n🔧 Testing multiple clips concatenation...")
    print("=" * 60)
    
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=output_path,
        title="스피드 복습",
        template_number=11
    )
    
    if success:
        print(f"✅ Multiple clips review created: {output_path}")
        
        # 길이 확인
        duration_result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', output_path],
            capture_output=True, text=True
        )
        duration = float(duration_result.stdout.strip())
        print(f"  Total duration: {duration:.2f} seconds")
        print("  (Expected: ~6-8 seconds for title + 2 clips)")
        
    else:
        print("❌ Multiple clips test failed")

if __name__ == "__main__":
    print("🚀 Starting fixed review clip tests...\n")
    
    # 단일 클립 테스트
    asyncio.run(test_fixed_review())
    
    # 여러 클립 테스트
    asyncio.run(test_multiple_clips())
    
    print("\n✅ All tests completed!")
    
    # 생성된 파일 목록
    print("\n📁 Generated files:")
    for file in ['test_fixed_output.mp4', 'test_multiple_clips.mp4']:
        if os.path.exists(file):
            size = os.path.getsize(file) / 1024
            print(f"  - {file} ({size:.1f} KB)")