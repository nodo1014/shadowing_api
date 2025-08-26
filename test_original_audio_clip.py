#!/usr/bin/env python3
"""
원본 오디오 스터디 클립 테스트
"""

import logging
from pathlib import Path
from template_video_encoder import TemplateVideoEncoder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_original_audio_clips():
    """원본 오디오를 사용하는 스터디 클립 테스트"""
    
    # Initialize encoder
    encoder = TemplateVideoEncoder()
    
    # Test video path
    test_video = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    # Test data
    subtitle_data = {
        'text_eng': "You will be Hunters.",
        'text_kor': "너희는 헌터가 될 거야.",
        'start_time': 50.0,
        'end_time': 52.5,
        'title_1': '',  
        'title_2': '',
        'title_3': ''
    }
    
    # Test templates
    test_templates = [
        ("template_study_original", "test_study_original.mp4", "Regular study with original audio"),
        ("template_study_shorts_original", "test_study_shorts_original.mp4", "Shorts study with original audio")
    ]
    
    for template_name, output_file, description in test_templates:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing: {description}")
        logger.info(f"Template: {template_name}")
        logger.info(f"Output: {output_file}")
        
        try:
            # Create output path
            output_path = Path("output/test_study_clips") / output_file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate clip
            success = encoder.create_from_template(
                template_name=template_name,
                media_path=test_video,
                subtitle_data=subtitle_data,
                output_path=str(output_path),
                start_time=subtitle_data['start_time'],
                end_time=subtitle_data['end_time'],
                save_individual_clips=False
            )
            
            if success:
                logger.info(f"✅ Successfully created {description}")
                logger.info(f"   Output: {output_path}")
            else:
                logger.error(f"❌ Failed to create {description}")
                
        except Exception as e:
            logger.error(f"❌ Error creating {description}: {e}", exc_info=True)
    
    logger.info(f"\n{'='*50}")
    logger.info("Original audio clip test completed!")

if __name__ == "__main__":
    test_original_audio_clips()