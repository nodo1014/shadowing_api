#!/usr/bin/env python3
"""
Test script for review clip only
"""

import asyncio
from review_clip_generator import ReviewClipGenerator

async def test_review_only():
    """리뷰 클립만 따로 테스트"""
    print("Testing review clip generation only...")
    
    # Test data
    clips_data = [
        {
            'text_eng': 'Hello, how are you?',
            'text_kor': '안녕하세요, 어떻게 지내세요?'
        },
        {
            'text_eng': "I've been waiting for you.",
            'text_kor': '널 기다리고 있었어.'
        }
    ]
    
    # Create generator
    generator = ReviewClipGenerator()
    
    # Output path
    output_path = "/home/kang/dev_amd/shadowing_maker_xls/test_review_only_output.mp4"
    
    # Generate review clip only
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=output_path,
        title="테스트 복습",
        template_number=11
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
    asyncio.run(test_review_only())