#!/usr/bin/env python3
"""Test blur background shorts template"""

from template_video_encoder import TemplateVideoEncoder
from pathlib import Path
import json

# Test data
test_data = {
    "media_path": "media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
    "media_url": "test.mp4",
    "subtitle_en": "media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].srt",
    "subtitle_ko": "media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].kor.srt",
    "start_time": 1208.94,
    "end_time": 1217.596,
    "text_eng": "In 400 years, you've never done a single thing that didn't serve yourself.",
    "text_kor": "넌 오로지 네게 득이 되는 일만 해 왔어",
    "keywords": ["serve yourself", "400 years"],
    "note": "serve yourself = 자신의 이익만 추구하다"
}

# Subtitle data format for encoder
subtitle_data = {
    "start_time": test_data["start_time"],
    "end_time": test_data["end_time"],
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

print("=== Creating Blur Background Shorts ===")
print(f"Source: {Path(test_data['media_path']).name}")
print(f"Duration: {test_data['end_time'] - test_data['start_time']:.1f}s")
print()

# Generate blur background version
print("--- Creating 블러 배경 버전 (shorts_template_blur) ---")
result = encoder.create_from_template(
    template_name='shorts_template_blur',
    media_path=test_data['media_path'],
    subtitle_data=subtitle_data,
    output_path=str(output_dir / "shorts_blur.mp4"),
    start_time=test_data['start_time'],
    end_time=test_data['end_time'],
    padding_before=0.5,
    padding_after=0.5,
    save_individual_clips=True
)

if result:
    print(f"✓ Success: {output_dir}/shorts_blur.mp4")
    
    # Extract preview frame
    import subprocess
    cmd = [
        'ffmpeg', '-i', str(output_dir / "shorts_blur.mp4"),
        '-ss', '00:00:05', '-vframes', '1', '-q:v', '2',
        '-y', str(output_dir / "preview_blur.png")
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✓ Preview saved: {output_dir}/preview_blur.png")
else:
    print("✗ Failed to create video")

print("\nDone!")