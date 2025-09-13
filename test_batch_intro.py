#!/usr/bin/env python3
"""
배치 인트로 비디오 생성 테스트 스크립트
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api"

def test_batch_with_intro():
    """인트로를 포함한 배치 비디오 생성 테스트"""
    
    # 1. 인트로 비디오 생성
    print("1. 인트로 비디오 생성 중...")
    intro_request = {
        "headerText": "Let's learn English patterns",
        "koreanText": "영어 패턴을 배워봅시다",
        "explanation": "오늘은 일상에서 자주 사용하는 표현들을 연습해보겠습니다",
        "template": "fade_in",
        "format": "shorts",
        "useBlur": True,
        "useGradient": True
    }
    
    # firstSentenceMediaInfo 추가 (배경 이미지용)
    # 실제 미디어 파일 경로가 필요합니다
    media_path = "/path/to/your/media.mp4"  # 실제 경로로 변경 필요
    if Path(media_path).exists():
        intro_request["firstSentenceMediaInfo"] = {
            "mediaPath": media_path,
            "startTime": 0.0
        }
    
    response = requests.post(f"{BASE_URL}/intro-videos", json=intro_request)
    if response.status_code != 200:
        print(f"인트로 생성 실패: {response.text}")
        return
    
    intro_data = response.json()
    intro_path = intro_data["video"]["videoFilePath"]
    print(f"인트로 생성 완료: {intro_path}")
    
    # 2. 배치 클립 생성
    print("\n2. 배치 클립 생성 중...")
    batch_request = {
        "clips": [
            {
                "start_time": 10.0,
                "end_time": 15.0,
                "text_en": "How are you doing?",
                "text_ko": "어떻게 지내세요?",
                "media_path": media_path
            },
            {
                "start_time": 20.0,
                "end_time": 25.0,
                "text_en": "I'm doing great, thanks!",
                "text_ko": "잘 지내고 있어요, 감사합니다!",
                "media_path": media_path
            }
        ],
        "template_number": 11,  # 쇼츠 템플릿
        "individual_clips": True,
        "title_1": "Daily Conversation",
        "title_2": "일상 대화"
    }
    
    response = requests.post(f"{BASE_URL}/clip/batch", json=batch_request)
    if response.status_code != 200:
        print(f"배치 생성 실패: {response.text}")
        return
    
    batch_data = response.json()
    combined_path = batch_data.get("combined_video_path")
    print(f"배치 생성 완료: {combined_path}")
    
    # 3. 인트로와 배치 비디오 병합
    print("\n3. 인트로와 배치 비디오 병합 중...")
    merge_request = {
        "videoPaths": [intro_path, combined_path],
        "outputFileName": "final_with_intro.mp4"
    }
    
    response = requests.post(f"{BASE_URL}/merge-videos", json=merge_request)
    if response.status_code != 200:
        print(f"병합 실패: {response.text}")
        return
    
    merge_data = response.json()
    final_path = merge_data["outputPath"]
    print(f"최종 비디오 생성 완료: {final_path}")
    
    return {
        "intro_video": intro_path,
        "batch_video": combined_path,
        "final_video": final_path
    }


if __name__ == "__main__":
    print("=== 배치 인트로 비디오 생성 테스트 ===")
    print("주의: 실제 미디어 파일 경로를 설정해야 합니다!")
    
    # 테스트 실행
    result = test_batch_with_intro()
    
    if result:
        print("\n=== 테스트 완료 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))