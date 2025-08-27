#!/usr/bin/env python3
"""
TTS 직접 테스트
"""
import asyncio
from edge_tts_util import EdgeTTSGenerator

async def test_tts():
    tts = EdgeTTSGenerator()
    
    # TTS 생성
    success = await tts.generate_tts_async(
        "You will be Hunters.",
        "test_tts_output.mp3"
    )
    
    if success:
        print("✅ TTS 생성 성공: test_tts_output.mp3")
        
        import subprocess
        # 오디오 확인
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', 'test_tts_output.mp3'],
            capture_output=True, text=True
        )
        print(f"Duration: {result.stdout.strip()}s")
    else:
        print("❌ TTS 생성 실패")

asyncio.run(test_tts())