#!/usr/bin/env python3

import subprocess
from pathlib import Path

# Create simple test with Tmon font directly specified
test_ass = """[Script Info]
Title: Font Test
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,/home/kang/dev_amd/shadowing_maker_xls/font/TmonMonsori.ttf,60,&H00D7FF&,&H000000FF,&H000000&,&H00000000,0,0,0,0,100,100,0,0,1,3,4,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,티몬 몬소리체 테스트
"""

# Save test ASS
with open("shorts_output/test_font.ass", "w", encoding="utf-8") as f:
    f.write(test_ass)

# Try different approaches
print("Testing font loading approaches...")

# 1. Direct font path in ASS
cmd = [
    'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:d=5',
    '-vf', 'ass=shorts_output/test_font.ass',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-y', 'shorts_output/test_direct.mp4'
]
subprocess.run(cmd, capture_output=True)

# 2. With fontsdir
font_path = Path("/home/kang/dev_amd/shadowing_maker_xls/font").absolute()
cmd = [
    'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:d=5',
    '-vf', f'ass=shorts_output/test_font.ass:fontsdir={font_path}',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-y', 'shorts_output/test_fontsdir.mp4'
]
subprocess.run(cmd, capture_output=True)

# Extract frames
for name in ['direct', 'fontsdir']:
    cmd = [
        'ffmpeg', '-i', f'shorts_output/test_{name}.mp4',
        '-ss', '00:00:01', '-vframes', '1', '-q:v', '2',
        '-y', f'shorts_output/test_{name}.png'
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✓ Created test_{name}.png")

print("\nDone!")