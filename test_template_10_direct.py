#!/usr/bin/env python3
"""
템플릿 10 자막 표시 직접 테스트
"""
import os
import sys
import tempfile
import logging
from pathlib import Path

# 프로젝트 경로 추가
sys.path.append(str(Path(__file__).parent))

from template_video_encoder import TemplateVideoEncoder

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_template_10_direct():
    """템플릿 10 자막 표시 직접 테스트"""
    print("=== 템플릿 10 자막 표시 직접 테스트 ===")
    
    encoder = TemplateVideoEncoder()
    
    # 테스트 데이터
    media_path = "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4"
    template_name = "template_original_shorts"  # 템플릿 10
    
    # 자막 데이터
    subtitle_data = {
        'template_number': 10,
        'start_time': 5.0,
        'end_time': 10.0,
        'text_eng': "Do you want to build a snowman?",
        'text_kor': "눈사람 만들래?",
        'keywords': ["snowman", "build"],
        'title_1': "Frozen Test",
        'title_2': "Template 10",
        'aspect_ratio': 'center'  # 기본값
    }
    
    # 출력 경로
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "test_template_10_subtitles.mp4"
    
    print(f"미디어: {media_path}")
    print(f"템플릿: {template_name}")
    print(f"구간: {subtitle_data['start_time']}s - {subtitle_data['end_time']}s")
    print(f"영어 자막: {subtitle_data['text_eng']}")
    print(f"한글 자막: {subtitle_data['text_kor']}")
    print(f"출력: {output_path}")
    print()
    
    # 비디오 생성
    try:
        success = encoder.create_from_template(
            template_name=template_name,
            media_path=media_path,
            subtitle_data=subtitle_data,
            output_path=str(output_path),
            start_time=subtitle_data['start_time'],
            end_time=subtitle_data['end_time'],
            save_individual_clips=False
        )
        
        if success:
            print("✅ 비디오 생성 성공!")
            print(f"출력 파일: {output_path}")
            
            # 파일 크기 확인
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"파일 크기: {size_mb:.2f} MB")
        else:
            print("❌ 비디오 생성 실패!")
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_template_10_direct()