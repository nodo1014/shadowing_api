#!/usr/bin/env python3
"""
Test script for study clip integration into new clipping system
"""

import asyncio
import logging
from pathlib import Path
from template_video_encoder import TemplateVideoEncoder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_study_clips():
    """Test study clip template integration"""
    
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
        'title_1': '',  # No titles for study clips
        'title_2': '',
        'title_3': ''
    }
    
    # Test templates
    test_templates = [
        ("template_study_preview", "test_study_preview.mp4", "Regular study preview clip"),
        ("template_study_review", "test_study_review.mp4", "Regular study review clip"),
        ("template_study_shorts_preview", "test_study_shorts_preview.mp4", "Shorts study preview clip"),
        ("template_study_shorts_review", "test_study_shorts_review.mp4", "Shorts study review clip")
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
                save_individual_clips=False  # No need for individual clips
            )
            
            if success:
                logger.info(f"✅ Successfully created {description}")
                logger.info(f"   Output: {output_path}")
            else:
                logger.error(f"❌ Failed to create {description}")
                
        except Exception as e:
            logger.error(f"❌ Error creating {description}: {e}", exc_info=True)
    
    logger.info(f"\n{'='*50}")
    logger.info("Study clip integration test completed!")

# Test via new clipping API
def test_via_api():
    """Test using the clipping API with template numbers"""
    import requests
    import json
    
    base_url = "http://localhost:8000/api/clips"
    
    # Test data
    test_requests = [
        {
            "template_number": 31,  # Study preview
            "description": "Study clip - preview via API"
        },
        {
            "template_number": 32,  # Study review
            "description": "Study clip - review via API"
        },
        {
            "template_number": 33,  # Shorts study preview
            "description": "Shorts study clip - preview via API"
        },
        {
            "template_number": 34,  # Shorts study review
            "description": "Shorts study clip - review via API"
        }
    ]
    
    for test_req in test_requests:
        logger.info(f"\nTesting: {test_req['description']}")
        
        # Create request
        clip_request = {
            "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
            "start_time": 50.0,
            "end_time": 52.5,
            "text_eng": "You will be Hunters.",
            "text_kor": "너희는 헌터가 될 거야.",
            "note": "",
            "keywords": [],
            "template_number": test_req["template_number"],
            "individual_clips": False
        }
        
        logger.info(f"Request: {json.dumps(clip_request, indent=2)}")
        
        # Note: This would require the API server to be running
        # response = requests.post(f"{base_url}/create", json=clip_request)
        # logger.info(f"Response: {response.json()}")

if __name__ == "__main__":
    # Test direct template usage
    asyncio.run(test_study_clips())
    
    # Show API usage example
    logger.info("\n" + "="*50)
    logger.info("API Usage Example:")
    logger.info("="*50)
    test_via_api()