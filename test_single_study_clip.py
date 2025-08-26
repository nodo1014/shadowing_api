#!/usr/bin/env python3
"""
단일 스터디 클립 테스트 - 직접 생성
"""
import asyncio
from img_tts_generator import ImgTTSGenerator
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_single_clip():
    """하나의 스터디 클립 생성 테스트"""
    
    generator = ImgTTSGenerator()
    
    # 테스트 비디오
    video_path = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    # 출력 경로
    output_dir = Path("output/test_study_clips")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 일반 미리보기 클립
    logger.info("Creating regular preview clip...")
    result = await generator.create_video(
        video_frame={
            'path': video_path,
            'time': 50.1,  # 50초 지점
            'crop': None   # 크롭 없음
        },
        texts=[
            {'text': '너희는 헌터가 될 거야.', 'style': {}},
            {'text': 'You will be Hunters.', 'style': {}}
        ],
        tts_config={
            'text': 'You will be Hunters.',
            'voice': 'en-US-AriaNeural',
            'rate': '+0%'  # 일반 속도
        },
        output_path=str(output_dir / "test_preview.mp4"),
        resolution=(1920, 1080),
        style_preset='subtitle',
        add_silence=0.5  # 일반 클립은 0.5초 무음
    )
    
    if result:
        logger.info("✅ Regular preview clip created successfully!")
    else:
        logger.error("❌ Failed to create regular preview clip")
    
    # 2. 쇼츠 복습 클립
    logger.info("\nCreating shorts review clip...")
    result = await generator.create_video(
        video_frame={
            'path': video_path,
            'time': 50.1,
            'crop': "crop='iw*0.7:ih:iw*0.15:0',scale='if(gt(iw,1080),1080,iw)':'if(gt(iw,1080),ih*1080/iw,ih)',pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        },
        texts=[
            {'text': '너희는 헌터가 될 거야.', 'style': {}},
            {'text': 'You will be Hunters.', 'style': {}}
        ],
        tts_config={
            'text': 'You will be Hunters.',
            'voice': 'en-US-AriaNeural',
            'rate': '-10%'  # 느린 속도 (복습용)
        },
        output_path=str(output_dir / "test_shorts_review.mp4"),
        resolution=(1080, 1920),
        style_preset='shorts',
        add_silence=0.3  # 쇼츠 클립은 0.3초 무음
    )
    
    if result:
        logger.info("✅ Shorts review clip created successfully!")
    else:
        logger.error("❌ Failed to create shorts review clip")

if __name__ == "__main__":
    asyncio.run(test_single_clip())