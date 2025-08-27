#!/usr/bin/env python3
"""
Direct API test for review mode
"""

import requests
import json
import time

# API endpoint
BASE_URL = "http://localhost:8080"

# Simple test request with review mode
test_request = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/Disney/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
    "template_number": 11,
    "individual_clips": True,
    "review": True,
    "title_1": "테스트",
    "clips": [
        {
            "start_time": 10.0,
            "end_time": 13.0,
            "text_eng": "Hello world",
            "text_kor": "안녕 세상",
            "note": "테스트",
            "keywords": []
        }
    ]
}

def test_api():
    print("Sending API request...")
    print(f"Request: {json.dumps(test_request, indent=2)}")
    
    try:
        response = requests.post(f"{BASE_URL}/api/clip/batch", json=test_request, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            job_id = result["job_id"]
            print(f"✓ Job submitted: {job_id}")
            
            # Monitor status
            for i in range(60):  # 60초 동안 모니터링
                try:
                    status_response = requests.get(f"{BASE_URL}/api/status/{job_id}", timeout=3)
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"[{i:2d}s] Status: {status['status']} - {status.get('message', '')}")
                        
                        if status["status"] in ["completed", "failed"]:
                            break
                    else:
                        print(f"Status check failed: {status_response.status_code}")
                        
                except requests.RequestException as e:
                    print(f"Status check error: {e}")
                
                time.sleep(1)
                
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.RequestException as e:
        print(f"✗ Request error: {e}")

if __name__ == "__main__":
    test_api()