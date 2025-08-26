#!/usr/bin/env python3
"""
Test user's exact request
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

request_data = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
    "clips": [
        {
            "start_time": 52.127,
            "end_time": 55.187999999999995,
            "text_eng": "You will be Hunters.",
            "text_kor": "너희는 헌터가 될 거야",
            "keywords": []
        }
    ],
    "note": "선택된 클립 - 1개 문장",
    "clipping_type": 1,
    "template_number": 11,
    "individual_clips": False,
    "study": "review",
    "title_1": "케데몽",
    "title_2": "트와이스 지짱"
}

print("Sending user's exact request...")
print(f"Study mode: {request_data['study']}")
print(f"Template: {request_data['template_number']}")
print(f"Individual clips: {request_data['individual_clips']}")
print("Expected: Study clip (스피드 복습) should be at the END")

try:
    response = requests.post(f"{BASE_URL}/api/clip/batch", json=request_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ Job submitted: {result['job_id']}")
        print(f"  Message: {result['message']}")
        
        # 작업 완료 대기
        for i in range(60):  # 60초 대기
            time.sleep(1)
            status_response = requests.get(f"{BASE_URL}/api/job/{result['job_id']}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"\r  Status: {status.get('status')} - Progress: {status.get('progress')}%", end='', flush=True)
                if status.get('status') == 'completed':
                    print(f"\n\n✓ Job completed!")
                    job_id = result['job_id']
                    print(f"\nOutput directory: /mnt/ssd1t/output/2025-08-26/{job_id}/")
                    print(f"\nChecking files...")
                    import os
                    output_dir = f"/mnt/ssd1t/output/2025-08-26/{job_id}/"
                    if os.path.exists(output_dir):
                        files = os.listdir(output_dir)
                        for file in files:
                            print(f"  - {file}")
                    break
                elif status.get('status') == 'failed':
                    print(f"\n\n✗ Job failed: {status.get('error')}")
                    break
    else:
        print(f"\n✗ Request failed: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.RequestException as e:
    print(f"\n✗ Request error: {e}")