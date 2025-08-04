#!/usr/bin/env python3
"""
Test blank_korean subtitle with note in top-left corner
"""
import sys
from pathlib import Path
from shadowing_maker.core.video.template_encoder import TemplateVideoEncoder

def test_blank_korean_with_note():
    """Test Template 3 with blank_korean subtitle that includes note"""
    
    # Test video
    test_video = "/mnt/qnap/media_eng/indexed_media/animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    
    # Subtitle data with note
    subtitle_data = {
        "text_eng": "Hello, how are you?",
        "text_kor": "안녕하세요, 어떻게 지내세요?",
        "note": "인사말 표현",  # This note should appear in top-left corner
        "keywords": ["Hello", "how"]
    }
    
    # Output path
    output_path = "/home/kang/dev_amd/shadowing_maker_xls/output/test_blank_korean_note.mp4"
    
    # Create encoder
    encoder = TemplateVideoEncoder()
    
    print("Testing blank_korean with note...")
    print(f"Note to display: '{subtitle_data['note']}'")
    print(f"Note style: Font size 24, White color, Top-left position")
    print(f"Output: {output_path}")
    
    # Test with Template 3 (which uses blank_korean)
    success = encoder.create_from_template(
        template_name="template_3",
        media_path=test_video,
        subtitle_data=subtitle_data,
        output_path=output_path,
        start_time=10.5,
        end_time=15.5,
        save_individual_clips=True
    )
    
    if success:
        print(f"\n✓ Successfully created video with blank_korean + note")
        print("\nCheck the output video:")
        print("- Blank English text (keywords replaced with underscores)")
        print("- Korean translation at bottom")
        print("- Note '인사말 표현' in top-left corner (white, size 24)")
        
        # Check individual clips
        clip_dir = Path(output_path).parent / "individual_clips"
        if clip_dir.exists():
            blank_kor_dir = clip_dir / "2_blank_kor"
            if blank_kor_dir.exists():
                clips = list(blank_kor_dir.glob("*.mp4"))
                print(f"\nblank_korean clips saved: {len(clips)} files in {blank_kor_dir}")
    else:
        print(f"\n✗ Failed to create video")
    
    return success

if __name__ == "__main__":
    test_blank_korean_with_note()