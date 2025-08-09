#!/usr/bin/env python3
"""
Create shorts videos using the new templates
"""
import os
import json
from pathlib import Path
from template_video_encoder import TemplateVideoEncoder
from ass_generator import ASSGenerator

# Test data from recent clipping
test_data = {
    "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
    "start_time": 671.079,
    "end_time": 677.935,
    "text_eng": "In 400 years, you've never done a single thing that didn't serve yourself.",
    "text_kor": "넌 오로지 네게 득이 되는 일만 해 왔어",
    "note": "serve yourself = 자신의 이익만 추구하다"
}

# Check if media file exists, otherwise create test video
if not os.path.exists(test_data["media_path"]):
    print("Creating test video...")
    import subprocess
    test_data["media_path"] = "/tmp/test_shorts_source.mp4"
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:duration=10',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        test_data["media_path"]
    ]
    subprocess.run(cmd, capture_output=True)

# Prepare subtitle data
subtitle_data = {
    "start_time": 0.0,
    "end_time": test_data["end_time"] - test_data["start_time"],
    "eng": test_data["text_eng"],
    "kor": test_data["text_kor"],
    "english": test_data["text_eng"],
    "korean": test_data["text_kor"],
    "text_eng": test_data["text_eng"],
    "text_kor": test_data["text_kor"],
    "note": test_data["note"]
}

# Create output directory
output_dir = Path("shorts_output")
output_dir.mkdir(exist_ok=True)

# Initialize encoder
encoder = TemplateVideoEncoder()

print("=== Creating Shorts Videos ===")
print(f"Source: {os.path.basename(test_data['media_path'])}")
print(f"Duration: {test_data['end_time'] - test_data['start_time']:.1f}s")
print(f"English: {test_data['text_eng'][:50]}...")
print(f"Korean: {test_data['text_kor']}")
print()

# Create both versions
templates = [
    ("shorts_template_crop", "중앙 크롭 버전"),
    ("shorts_template_fit", "전체 화면 버전")
]

for template_name, description in templates:
    print(f"\n--- Creating {description} ({template_name}) ---")
    
    output_path = str(output_dir / f"shorts_{template_name.split('_')[-1]}.mp4")
    
    try:
        success = encoder.create_from_template(
            template_name=template_name,
            media_path=test_data["media_path"],
            subtitle_data=subtitle_data,
            output_path=output_path,
            start_time=test_data["start_time"],
            end_time=test_data["end_time"],
            save_individual_clips=True
        )
        
        if success:
            print(f"✓ Success: {output_path}")
            
            # Extract a preview frame
            preview_path = str(output_dir / f"preview_{template_name.split('_')[-1]}.png")
            import subprocess
            cmd = [
                'ffmpeg', '-y',
                '-i', output_path,
                '-ss', '3',
                '-frames:v', '1',
                preview_path
            ]
            subprocess.run(cmd, capture_output=True)
            print(f"✓ Preview saved: {preview_path}")
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n=== Creating Title Test ===")
# Create title overlay for testing
title_generator = ASSGenerator()
title_path = str(output_dir / "shorts_title.ass")
title_generator.generate_shorts_title(title_path, "📺 스크린 잉글리쉬", duration=10.0)
print(f"✓ Title ASS created: {title_path}")

# Create a combined version with title
print("\n--- Creating version with title overlay ---")
if os.path.exists(str(output_dir / "shorts_crop.mp4")):
    cmd = [
        'ffmpeg', '-y',
        '-i', str(output_dir / "shorts_crop.mp4"),
        '-vf', f"ass={title_path}",
        '-c:a', 'copy',
        str(output_dir / "shorts_crop_with_title.mp4")
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Created version with title: shorts_crop_with_title.mp4")
    else:
        print(f"✗ Failed to add title: {result.stderr}")

print("\n=== Summary ===")
print(f"Output directory: {output_dir}")
print("Files created:")
for file in sorted(output_dir.glob("*.mp4")):
    size_mb = file.stat().st_size / (1024 * 1024)
    print(f"  - {file.name} ({size_mb:.1f} MB)")
for file in sorted(output_dir.glob("*.png")):
    print(f"  - {file.name} (preview)")