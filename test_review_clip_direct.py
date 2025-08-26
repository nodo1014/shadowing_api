#!/usr/bin/env python3
"""
Direct test of review clip generation
"""

import asyncio
from review_clip_generator import ReviewClipGenerator

async def test_review_clip():
    generator = ReviewClipGenerator()
    
    clips_data = [
        {
            'text_eng': 'You will be Hunters.',
            'text_kor': '너희는 헌터가 될 거야'
        }
    ]
    
    output_path = 'test_review_output.mp4'
    
    print("Creating review clip...")
    success = await generator.create_review_clip(
        clips_data=clips_data,
        output_path=output_path,
        title="스피드 복습",
        template_number=11  # 쇼츠
    )
    
    if success:
        print(f"✓ Review clip created: {output_path}")
        
        # Check if it has audio
        import subprocess
        cmd = ['ffprobe', '-v', 'error', '-show_streams', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("\nStream info:")
        has_video = False
        has_audio = False
        for line in result.stdout.split('\n'):
            if 'codec_type=video' in line:
                has_video = True
            elif 'codec_type=audio' in line:
                has_audio = True
        
        print(f"  Video: {'✓' if has_video else '✗'}")
        print(f"  Audio: {'✓' if has_audio else '✗'}")
        
        if not has_audio:
            print("\n⚠️  WARNING: No audio stream found!")
    else:
        print("✗ Failed to create review clip")

if __name__ == "__main__":
    asyncio.run(test_review_clip())