#!/usr/bin/env python3
"""Test sequential ID generation"""
import requests
import json
import time

# API endpoint
BASE_URL = "http://localhost:8080"

# Test single clip
test_data = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/22.Jump.Street.2014.1080p.BluRay.x264.YIFY.mp4",
    "start_time": 10.0,
    "end_time": 15.0,
    "text_eng": "This is a test clip with sequential folder ID",
    "text_kor": "순차 폴더 ID를 사용한 테스트 클립입니다",
    "note": "Testing sequential folder naming",
    "template_number": 1
}

print("Testing sequential folder ID generation...")
print(f"Sending request to {BASE_URL}/api/clip")

# Send multiple requests to see sequential numbering
for i in range(3):
    response = requests.post(f"{BASE_URL}/api/clip", json=test_data)
    if response.status_code == 200:
        result = response.json()
        print(f"\nRequest {i+1} successful:")
        print(f"  Job ID: {result['job_id']}")
        print(f"  Status: {result['status']}")
        
        # Check job status
        time.sleep(1)
        status_response = requests.get(f"{BASE_URL}/api/job/{result['job_id']}")
        if status_response.status_code == 200:
            status = status_response.json()
            folder_id = status.get('folder_id', 'Not found')
            print(f"  Folder ID: {folder_id}")
    else:
        print(f"\nRequest {i+1} failed: {response.status_code}")
        print(response.text)
    
    time.sleep(0.5)

print("\nDone! Check the output directory to see the sequential folder names.")
print("Expected structure: /output/YYYY-MM-DD/001, /output/YYYY-MM-DD/002, etc.")