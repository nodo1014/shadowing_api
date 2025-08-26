#!/usr/bin/env python3
"""
Test review_mode API parameter
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_review_mode(mode="review"):
    """리뷰 모드 API 테스트"""
    
    request_data = {
        "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
        "template_number": 11,
        "individual_clips": True,
        "review": True,
        "review_mode": mode,  # "preview" or "review"
        "title_1": "영어 표현 학습",
        "clips": [
            {
                "start_time": 10.0,
                "end_time": 13.0,
                "text_eng": "Let it go",
                "text_kor": "다 잊어",
                "note": "",
                "keywords": []
            },
            {
                "start_time": 20.0,
                "end_time": 23.0,
                "text_eng": "I can't hold it back anymore",
                "text_kor": "더 이상 참을 수 없어",
                "note": "",
                "keywords": []
            }
        ]
    }
    
    print(f"\n{'='*50}")
    print(f"Testing review_mode: {mode}")
    print(f"Expected title: {'스피드 미리보기' if mode == 'preview' else '스피드 복습'}")
    print(f"Expected position: {'맨 앞' if mode == 'preview' else '맨 뒤'}")
    print(f"{'='*50}\n")
    
    try:
        response = requests.post(f"{BASE_URL}/api/clip/batch", json=request_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Job submitted: {result['job_id']}")
            print(f"  Message: {result['message']}")
            
            # 잠시 대기 후 상태 확인
            time.sleep(2)
            status_response = requests.get(f"{BASE_URL}/api/job/{result['job_id']}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"  Status: {status.get('status')}")
                print(f"  Progress: {status.get('progress')}%")
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.RequestException as e:
        print(f"✗ Request error: {e}")

if __name__ == "__main__":
    # Preview 모드 테스트 (스피드 미리보기 - 앞에 붙이기)
    test_review_mode("preview")
    
    # Review 모드 테스트 (스피드 복습 - 뒤에 붙이기)
    test_review_mode("review")
    
    # 기본값 테스트 (review_mode 생략)
    print("\n테스트: review_mode 생략 시 기본값")
    test_review_mode("review")