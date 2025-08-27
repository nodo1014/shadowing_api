#!/usr/bin/env python3
"""
Standalone test for hybrid review generator
"""

import asyncio
from hybrid_review_generator import HybridReviewGenerator

async def test_review_generator():
    """Test hybrid review generator"""
    print("Testing hybrid review generator...")
    
    # Test data
    clips_data = [
        {
            'text_eng': 'Hello, how are you?',
            'text_kor': '안녕하세요, 어떻게 지내세요?'
        },
        {
            'text_eng': "I've been waiting for you.",
            'text_kor': '널 기다리고 있었어.'
        },
        {
            'text_eng': 'Thank you for everything.',
            'text_kor': '모든 것에 감사합니다.'
        }
    ]
    
    # Create generator
    generator = HybridReviewGenerator()
    
    # Test video path (using a real media file)
    test_media = "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4"
    
    # Output path
    output_path = "/home/kang/dev_amd/shadowing_maker_xls/test_review_output.mp4"
    
    # Generate review clip
    success = await generator.create_review_clip(
        clips_data=clips_data,
        media_path=test_media,
        output_path=output_path,
        title="Speed Review Test",
        template_number=11  # Shorts
    )
    
    if success:
        print(f"✓ Review clip created successfully: {output_path}")
        
        # Check file size
        import os
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  File size: {size_mb:.2f} MB")
    else:
        print("✗ Failed to create review clip")

if __name__ == "__main__":
    asyncio.run(test_review_generator())