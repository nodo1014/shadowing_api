#!/usr/bin/env python3
"""
Test script for batch clipping with review mode
"""

import requests
import time
import json

# API endpoint
BASE_URL = "http://localhost:8000"

# Test batch request with review mode
batch_request = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
    "template_number": 11,  # Shorts template
    "individual_clips": True,
    "review": True,  # Enable review mode
    "title_1": "영어 마스터하기",
    "title_2": "오늘의 표현들",
    "clips": [
        {
            "start_time": 10.5,
            "end_time": 15.5,
            "text_eng": "Hello, how are you doing?",
            "text_kor": "안녕하세요, 어떻게 지내세요?",
            "note": "인사하기",
            "keywords": ["Hello", "doing"]
        },
        {
            "start_time": 20.0,
            "end_time": 25.0,
            "text_eng": "I've been waiting for you.",
            "text_kor": "널 기다리고 있었어.",
            "note": "현재완료진행형",
            "keywords": ["waiting", "been"]
        },
        {
            "start_time": 30.0,
            "end_time": 35.0,
            "text_eng": "Thank you for everything.",
            "text_kor": "모든 것에 감사합니다.",
            "note": "감사 표현",
            "keywords": ["Thank", "everything"]
        }
    ]
}

def test_batch_review():
    """Test batch clipping with review mode"""
    print("Testing batch clipping with review mode...")
    print(f"Template: {batch_request['template_number']}")
    print(f"Review mode: {batch_request['review']}")
    print(f"Number of clips: {len(batch_request['clips'])}")
    
    # Send request
    response = requests.post(f"{BASE_URL}/api/clip/batch", json=batch_request)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"\n✓ Job submitted successfully: {job_id}")
        print(f"  Message: {result['message']}")
        
        # Poll for status
        print("\nChecking job status...")
        while True:
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"\r  Status: {status['status']} ({status.get('progress', 0)}%) - {status.get('message', '')}    ", end="")
                
                if status["status"] == "completed":
                    print(f"\n\n✓ Job completed!")
                    print(f"  Output files: {status.get('output_files', [])}")
                    print(f"  Combined video: {status.get('combined_video', 'N/A')}")
                    break
                elif status["status"] == "failed":
                    print(f"\n\n✗ Job failed!")
                    print(f"  Error: {status.get('error', 'Unknown error')}")
                    break
                
                time.sleep(2)
            else:
                print(f"\n✗ Failed to get status: {status_response.text}")
                break
    else:
        print(f"✗ Failed to submit job: {response.text}")

if __name__ == "__main__":
    test_batch_review()