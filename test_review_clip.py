#!/usr/bin/env python3
"""
개선된 리뷰 클립 생성 테스트
- NotoSans Bold 폰트
- 두꺼운 테두리
- Aria 음성, 느린 속도
"""
import asyncio
import logging
from review_clip_generator import ReviewClipGenerator

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_review_clip():
    """리뷰 클립 생성 테스트"""
    
    generator = ReviewClipGenerator()
    
    # 테스트 데이터
    clips_data = [
        {
            'text_eng': 'You will be Hunters.',
            'text_kor': '너희는 헌터가 될 거야.'
        },
        {
            'text_eng': 'The world needs heroes.',
            'text_kor': '세상은 영웅이 필요해.'
        }
    ]
    
    # 원본 비디오
    video_path = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    # 타임스탬프 (예시)
    clip_timestamps = [
        (50.0, 52.5),   # 첫 번째 문장
        (53.0, 56.0)    # 두 번째 문장
    ]
    
    # 출력 경로
    output_path = "test_review_clip_improved.mp4"
    
    # 리뷰 클립 생성 (정지 프레임 배경 사용)
    print("🎬 개선된 리뷰 클립 생성 시작...")
    print("📌 설정:")
    print("   - 폰트: NotoSans CJK Bold")
    print("   - 테두리: 5px (두껍게)")
    print("   - 영어 음성: Aria (-10% 속도)")
    print("   - 배경: 원본 비디오 정지 프레임")
    
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=output_path,
        title="스피드 복습",
        template_number=11,  # 쇼츠 템플릿
        video_path=video_path,
        clip_timestamps=clip_timestamps
    )
    
    if success:
        print(f"\n✅ 리뷰 클립 생성 성공: {output_path}")
        
        # 클립 정보 확인
        import subprocess
        
        # 비디오 정보
        cmd = ['ffprobe', '-v', 'error', '-show_streams', '-select_streams', 'v:0', 
               '-show_entries', 'stream=width,height,codec_name', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"\n📊 비디오 정보:")
        print(result.stdout)
        
        # 오디오 볼륨 확인
        print("\n🔊 오디오 볼륨 분석:")
        subprocess.run(['ffmpeg', '-i', output_path, '-af', 'volumedetect', '-f', 'null', '-'],
                       stderr=subprocess.PIPE)
        
    else:
        print("❌ 리뷰 클립 생성 실패")

if __name__ == "__main__":
    asyncio.run(test_review_clip())