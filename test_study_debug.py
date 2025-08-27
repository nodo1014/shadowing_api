#!/usr/bin/env python3
"""
Debug study mode API
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

# Review 모드 테스트 (뒤에 붙여야 함)
request_data = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
    "template_number": 1,
    "individual_clips": True,
    "title_1": "Debug Study Test",
    "study": "review",  # 명시적으로 review 설정
    "clips": [
        {
            "start_time": 118.242,
            "end_time": 121.245,
            "text_eng": "You will be Hunters.",
            "text_kor": "너희는 헌터가 될 거야",
            "note": "",
            "keywords": []
        }
    ]
}

print("Sending request with study='review'...")
print(f"Study mode: {request_data['study']}")
print("Expected: Study clip should be at the END")

try:
    response = requests.post(f"{BASE_URL}/api/clip/batch", json=request_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ Job submitted: {result['job_id']}")
        print(f"  Message: {result['message']}")
        
        # 상태 확인
        for i in range(30):  # 30초 대기
            time.sleep(1)
            status_response = requests.get(f"{BASE_URL}/api/job/{result['job_id']}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"\r  Status: {status.get('status')} - Progress: {status.get('progress')}%", end='', flush=True)
                if status.get('status') == 'completed':
                    print(f"\n\n✓ Job completed!")
                    print(f"  Check logs: grep '{result['job_id']}' /home/kang/dev_amd/shadowing_maker_xls/logs/clipping_api.log")
                    break
                elif status.get('status') == 'failed':
                    print(f"\n\n✗ Job failed: {status.get('error')}")
                    break
    else:
        print(f"\n✗ Request failed: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.RequestException as e:
    print(f"\n✗ Request error: {e}")