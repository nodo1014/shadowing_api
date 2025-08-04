#!/usr/bin/env python3
"""
Test Template 1 actual implementation
"""
import sys
import json
from pathlib import Path
from template_video_encoder import TemplateVideoEncoder

def test_template1():
    """Test Template 1 with actual implementation"""
    
    # Test video and subtitle data
    test_video = "/mnt/qnap/media_eng/indexed_media/animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    subtitle_data = {
        "text_eng": "Hello, how are you?",
        "text_kor": "안녕하세요, 어떻게 지내세요?",
        "note": "인사하는 표현",
        "keywords": ["Hello", "how"]
    }
    
    # Output path
    output_path = "/home/kang/dev_amd/shadowing_maker_xls/output/test_template1_real.mp4"
    
    # Create encoder
    encoder = TemplateVideoEncoder()
    
    print("Testing Template 1 encoding...")
    print(f"Input video: {test_video}")
    print(f"Output path: {output_path}")
    print(f"Subtitle data: {json.dumps(subtitle_data, ensure_ascii=False, indent=2)}")
    
    # Test with Template 1
    success = encoder.create_from_template(
        template_name="template_1",
        media_path=test_video,
        subtitle_data=subtitle_data,
        output_path=output_path,
        start_time=10.5,
        end_time=15.5,
        save_individual_clips=True
    )
    
    if success:
        print(f"\n✓ Successfully created Template 1 video: {output_path}")
        print("\nPlease check:")
        print("1. If all 5 segments show actual video movement")
        print("2. If any segments are frozen/still frames")
        print("3. Check individual clips in output/individual_clips/")
        
        # Check individual clips
        clip_dir = Path(output_path).parent / "individual_clips"
        if clip_dir.exists():
            print(f"\nIndividual clips saved in: {clip_dir}")
            for folder in sorted(clip_dir.iterdir()):
                if folder.is_dir():
                    clips = list(folder.glob("*.mp4"))
                    print(f"  {folder.name}: {len(clips)} clips")
    else:
        print(f"\n✗ Failed to create Template 1 video")
    
    return success

if __name__ == "__main__":
    test_template1()