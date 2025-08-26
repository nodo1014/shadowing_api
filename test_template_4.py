#!/usr/bin/env python3
"""
Template 4 테스트 스크립트
정지화면+한글TTS → 70%속도 → 100%속도(2회)
"""
import logging
from template_video_encoder import TemplateVideoEncoder
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_template_4():
    """Template 4 테스트"""
    
    # 테스트 비디오
    video_path = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    # 자막 데이터
    subtitle_data = {
        'text_eng': 'You will be Hunters.',
        'text_kor': '너희는 헌터가 될 거야.',
        'start_time': 50.1,
        'end_time': 52.6
    }
    
    # 출력 경로
    output_path = "output/test_template_4/template_4_test.mp4"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # 인코더 생성
    encoder = TemplateVideoEncoder()
    
    logger.info("Testing template_4...")
    logger.info(f"Video: {video_path}")
    logger.info(f"Text: {subtitle_data['text_eng']} / {subtitle_data['text_kor']}")
    logger.info(f"Time: {subtitle_data['start_time']}s - {subtitle_data['end_time']}s")
    
    # Template 4 실행
    result = encoder.create_from_template(
        template_name='template_4',
        media_path=video_path,
        subtitle_data=subtitle_data,
        output_path=output_path,
        start_time=subtitle_data['start_time'],
        end_time=subtitle_data['end_time'],
        padding_before=0.0,  # 패딩 없음
        padding_after=0.0,   # 패딩 없음
        save_individual_clips=True
    )
    
    if result:
        logger.info("✅ Template 4 테스트 성공!")
        logger.info(f"출력 파일: {output_path}")
        
        # 개별 클립 확인
        individual_dir = Path(output_path).parent / "individual_clips"
        if individual_dir.exists():
            logger.info("\n생성된 개별 클립:")
            for clip_dir in sorted(individual_dir.iterdir()):
                if clip_dir.is_dir():
                    logger.info(f"  {clip_dir.name}:")
                    for clip_file in sorted(clip_dir.glob("*.mp4")):
                        logger.info(f"    - {clip_file.name}")
    else:
        logger.error("❌ Template 4 테스트 실패!")

if __name__ == "__main__":
    test_template_4()