#!/usr/bin/env python3
"""
Test template fix - verify templates 1, 2, 3 are working
"""
import json
from template_video_encoder import TemplateVideoEncoder

def test_templates():
    """Test regular templates"""
    
    # Test video path
    test_video = "/home/kang/dev_amd/shadowing_maker_xls/test_videos/test_clip.mp4"
    
    # Test subtitle data
    subtitle_data = {
        "text_eng": "This is a test sentence.",
        "text_kor": "이것은 테스트 문장입니다.",
        "note": "테스트 노트",
        "keywords": ["test", "sentence"]
    }
    
    # Create encoder
    encoder = TemplateVideoEncoder()
    
    # Test each template
    for template_num in [1, 2, 3]:
        template_name = f"template_{template_num}"
        output_path = f"/tmp/test_{template_name}.mp4"
        
        print(f"\n{'='*60}")
        print(f"Testing {template_name}...")
        print(f"Output: {output_path}")
        
        # Load and check template
        template = encoder.get_template(template_name)
        if template:
            print(f"Template loaded: {template.get('name', 'Unknown')}")
            print(f"Description: {template.get('description', 'No description')}")
            print(f"Clips structure: {len(template.get('clips', []))} clips")
            
            # Try to create video
            success = encoder.create_from_template(
                template_name=template_name,
                media_path=test_video,
                subtitle_data=subtitle_data,
                output_path=output_path,
                start_time=0,
                end_time=3,
                save_individual_clips=False
            )
            
            if success:
                print(f"✓ {template_name} - SUCCESS")
            else:
                print(f"✗ {template_name} - FAILED")
        else:
            print(f"✗ {template_name} - NOT FOUND")

if __name__ == "__main__":
    test_templates()