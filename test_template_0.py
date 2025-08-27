#!/usr/bin/env python3
"""
Template 0 및 Template 10 테스트
"""
import requests
import json
import time

# API 베이스 URL
BASE_URL = "http://localhost:8000/api"

# 테스트 데이터 - 일반 template_0
test_data_normal = {
    "media_path": "/home/kang/downloads/study/video/ted_classic_20_video2_1920x1080_30fps.mp4",
    "start_time": 50.0,
    "end_time": 55.0,
    "template_number": 0,
    "subtitles": [
        {
            "start": 50.1,
            "end": 52.5,
            "eng": "You will be Hunters.",
            "kor": "너희는 헌터가 될 거야."
        },
        {
            "start": 52.6,
            "end": 54.9,
            "eng": "But you will be much more.",
            "kor": "하지만 훨씬 더 많은 것이 될 거야."
        }
    ]
}

# 테스트 데이터 - 쇼츠 template_10
test_data_shorts = {
    "media_path": "/home/kang/downloads/study/video/ted_classic_20_video2_1920x1080_30fps.mp4",
    "start_time": 50.0,
    "end_time": 55.0,
    "template_number": 10,  # 쇼츠용
    "subtitles": [
        {
            "start": 50.1,
            "end": 52.5,
            "eng": "You will be Hunters.",
            "kor": "너희는 헌터가 될 거야."
        },
        {
            "start": 52.6,
            "end": 54.9,
            "eng": "But you will be much more.",
            "kor": "하지만 훨씬 더 많은 것이 될 거야."
        }
    ]
}

def test_extract_range(test_data, test_name):
    """구간 추출 테스트"""
    print(f"\n{'='*50}")
    print(f"Testing: {test_name}")
    print(f"Template: {test_data['template_number']}")
    print(f"{'='*50}")
    
    # 요청 전송
    response = requests.post(f"{BASE_URL}/extract/range", json=test_data)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result['job_id']
        print(f"✅ Job created: {job_id}")
        
        # 작업 상태 확인
        while True:
            status_response = requests.get(f"{BASE_URL}/job/{job_id}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"Status: {status['status']} - {status['progress']}% - {status.get('message', '')}")
                
                if status['status'] == 'completed':
                    print(f"✅ Completed! Output: {status.get('output_file', 'N/A')}")
                    break
                elif status['status'] == 'failed':
                    print(f"❌ Failed: {status.get('error', 'Unknown error')}")
                    break
                
                time.sleep(1)
            else:
                print(f"❌ Failed to get status: {status_response.text}")
                break
    else:
        print(f"❌ Failed to create job: {response.text}")

if __name__ == "__main__":
    print("🎬 Template 0/10 Test Script")
    
    # Template 0 테스트 (일반)
    test_extract_range(test_data_normal, "Template 0 - Normal (1920x1080)")
    
    # Template 10 테스트 (쇼츠)
    test_extract_range(test_data_shorts, "Template 10 - Shorts (1080x1920)")