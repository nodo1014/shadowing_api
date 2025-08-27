#!/usr/bin/env python3
"""
Test preview and review positioning
"""

import requests
import json

BASE_URL = "http://localhost:8080"

# Preview 테스트 (앞에 붙이기)
preview_request = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
    "template_number": 11,
    "individual_clips": True,
    "review": True,
    "review_mode": "preview",  # Preview - 앞에 붙이기
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

# Review 테스트 (뒤에 붙이기)
review_request = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
    "template_number": 11,
    "individual_clips": True,
    "review": True,
    "review_mode": "review",  # Review - 뒤에 붙이기 (기본값)
    "title_1": "영어 표현 학습",
    "clips": preview_request["clips"]  # 같은 클립 사용
}

def test_review_mode(test_type="preview"):
    """리뷰 클립 모드 테스트"
    
    request_data = preview_request if test_type == "preview" else review_request
    
    print(f"\nTesting {test_type.upper()} mode...")
    print(f"Review mode: {request_data['review_mode']}")
    print(f"Expected title: {'스피드 미리보기' if test_type == 'preview' else '스피드 복습'}")
    
    try:
        response = requests.post(f"{BASE_URL}/api/clip/batch", json=request_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Job submitted: {result['job_id']}")
            print(f"  Message: {result['message']}")
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.RequestException as e:
        print(f"✗ Request error: {e}")

if __name__ == "__main__":
    # Preview 테스트 (앞에 붙이기)
    test_review_mode("preview")
    
    # Review 테스트 (뒤에 붙이기)
    test_review_mode("review")