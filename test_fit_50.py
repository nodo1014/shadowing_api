#!/usr/bin/env python3

from template_video_encoder import TemplateVideoEncoder
from pathlib import Path
import subprocess

test_data = {
    "media_path": "media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
    "start_time": 1208.94,
    "end_time": 1217.596,
    "text_eng": "In 400 years, you've never done a single thing that didn't serve yourself.",
    "text_kor": "넌 오로지 네게 득이 되는 일만 해 왔어",
    "note": "serve yourself = 자신의 이익만 추구하다"
}

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

output_dir = Path("shorts_output")
output_dir.mkdir(exist_ok=True)

encoder = TemplateVideoEncoder()

print("=== Testing True 50% Height Fit Mode ===")

result = encoder.create_from_template(
    template_name='shorts_template_fit',
    media_path=test_data['media_path'],
    subtitle_data=subtitle_data,
    output_path=str(output_dir / "shorts_fit_true50.mp4"),
    start_time=test_data['start_time'],
    end_time=test_data['end_time'],
    padding_before=0.5,
    padding_after=0.5,
    save_individual_clips=False
)

if result:
    print(f"✓ Success: {output_dir}/shorts_fit_true50.mp4")
    
    # Extract preview at 5 seconds
    cmd = [
        'ffmpeg', '-i', str(output_dir / "shorts_fit_true50.mp4"),
        '-ss', '00:00:05', '-vframes', '1', '-q:v', '2',
        '-y', str(output_dir / "preview_fit_true50.png")
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✓ Preview saved: {output_dir}/preview_fit_true50.png")

print("\nDone!")