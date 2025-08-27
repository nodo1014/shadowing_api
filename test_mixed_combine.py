#!/usr/bin/env python3
"""
Test mixed template with combine
"""
import requests
import json
import time

def test_mixed_combine():
    url = "http://localhost:8080/api/clip/mixed"
    
    data = {
        "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "clips": [
            {
                "start_time": 29.821,
                "end_time": 46.838,
                "template_number": 0,
                "subtitles": [
                    {
                        "start": 29.821,
                        "end": 33.658,
                        "eng": "Huntrix!",
                        "kor": "헌트릭스!"
                    },
                    {
                        "start": 33.742,
                        "end": 39.706,
                        "eng": "Huntrix!",
                        "kor": "헌트릭스!"
                    },
                    {
                        "start": 45.545,
                        "end": 46.838,
                        "eng": "Huntrix!",
                        "kor": "헌트릭스!"
                    }
                ]
            },
            {
                "start_time": 46.921,
                "end_time": 52.343,
                "template_number": 1,
                "text_eng": "The world will know you as pop stars, but you will be much more than that.",
                "text_kor": "세상은 너희를 팝 스타로 알겠지만",
                "keywords": [
                    "that",
                    "more than",
                    "will know",
                    "will be"
                ]
            },
            {
                "start_time": 52.427,
                "end_time": 54.888,
                "template_number": 0,
                "subtitles": [
                    {
                        "start": 52.427,
                        "end": 54.888,
                        "eng": "You will be Hunters.",
                        "kor": "너희는 헌터가 될 거야"
                    }
                ]
            }
        ],
        "combine": True,
        "title_1": "좀 되라..",
        "title_2": "으잉?"
    }
    
    print("Sending request to:", url)
    
    try:
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print(f"\n✓ Job created: {job_id}")
            
            # Poll for status
            print("\nPolling for status...")
            for i in range(60):
                time.sleep(1)
                status_response = requests.get(f"http://localhost:8080/api/status/{job_id}")
                
                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"[{i+1}s] {status.get('status')} - {status.get('message')}")
                    
                    if status.get('status') == 'completed':
                        print("\n✓ Success!")
                        print(f"Output files: {status.get('output_files', [])}")
                        print(f"Combined file: {status.get('combined_file')}")
                        break
                    elif status.get('status') == 'failed':
                        print("\n✗ Failed!")
                        print(f"Error: {status.get('error')}")
                        break
        else:
            print(f"\n✗ Request failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    test_mixed_combine()