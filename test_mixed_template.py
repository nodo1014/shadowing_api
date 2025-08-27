#!/usr/bin/env python3
"""
Test mixed template API
"""
import requests
import json
import time

def test_mixed_template_api():
    """Test the mixed template endpoint"""
    
    # API endpoint
    base_url = "http://localhost:8000"
    
    # Test data
    media_path = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-%5BYTS.MX%5D.mp4"
    
    # Mixed template request with different templates
    request_data = {
        "media_path": media_path,
        "clips": [
            # Template 0: 구간 추출 (원본 스타일)
            {
                "start_time": 60.0,
                "end_time": 65.0,
                "template_number": 0,
                "subtitles": [
                    {
                        "start": 60.5,
                        "end": 62.0,
                        "eng": "What are you doing here?",
                        "kor": "여기서 뭐 하는 거야?"
                    },
                    {
                        "start": 62.5,
                        "end": 64.5,
                        "eng": "I'm looking for someone.",
                        "kor": "누군가를 찾고 있어."
                    }
                ]
            },
            # Template 1: 기본 학습
            {
                "start_time": 70.0,
                "end_time": 73.0,
                "template_number": 1,
                "text_eng": "This is important.",
                "text_kor": "이것은 중요해.",
                "note": "강조 표현"
            },
            # Template 2: 키워드 블랭크
            {
                "start_time": 80.0,
                "end_time": 83.0,
                "template_number": 2,
                "text_eng": "Can you help me with this?",
                "text_kor": "이거 좀 도와줄 수 있어?",
                "keywords": ["help"]
            },
            # Template 0 again: 다시 구간 추출
            {
                "start_time": 90.0,
                "end_time": 95.0,
                "template_number": 0,
                "subtitles": [
                    {
                        "start": 90.5,
                        "end": 92.0,
                        "eng": "Of course I can.",
                        "kor": "물론이지."
                    },
                    {
                        "start": 93.0,
                        "end": 94.5,
                        "eng": "Just tell me what you need.",
                        "kor": "필요한 게 뭔지 말해봐."
                    }
                ]
            }
        ],
        "combine": True,
        "transitions": False
    }
    
    print("Testing Mixed Template API...")
    print(f"Media: {media_path}")
    print(f"Clips: {len(request_data['clips'])} clips with templates: {[c['template_number'] for c in request_data['clips']]}")
    
    # Send request
    try:
        response = requests.post(
            f"{base_url}/api/clip/mixed",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print(f"\nJob created: {job_id}")
            print(f"Status: {result.get('status')}")
            print(f"Message: {result.get('message')}")
            
            # Poll for status
            print("\nPolling for job status...")
            for i in range(30):  # Poll for up to 30 seconds
                time.sleep(1)
                status_response = requests.get(f"{base_url}/api/status/{job_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"[{i+1}s] Status: {status_data.get('status')} - {status_data.get('message')}")
                    
                    if status_data.get('status') == 'completed':
                        print("\n✓ Job completed successfully!")
                        print(f"Output files: {status_data.get('output_files', [])}")
                        if status_data.get('combined_file'):
                            print(f"Combined file: {status_data.get('combined_file')}")
                        break
                    elif status_data.get('status') == 'failed':
                        print("\n✗ Job failed!")
                        print(f"Error: {status_data.get('error')}")
                        break
                else:
                    print(f"Failed to get status: {status_response.status_code}")
                    
        else:
            print(f"\n✗ Request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    test_mixed_template_api()