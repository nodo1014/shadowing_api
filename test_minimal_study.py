#!/usr/bin/env python3
"""
최소한의 스터디 클립 테스트
"""
import asyncio
from review_clip_generator import ReviewClipGenerator

# 스터디 클립만 생성
async def main():
    generator = ReviewClipGenerator()
    await generator.create_review_clip(
        clips_data=[{"text_eng": "You will be Hunters.", "text_kor": "너희는 헌터가 될 거야"}],
        output_path="study_test.mp4",
        title="스피드 복습",
        template_number=11
    )
    print("생성 완료: study_test.mp4")

asyncio.run(main())