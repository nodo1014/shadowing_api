#!/usr/bin/env python3
"""
Test extract range API
"""
import requests
import json
import time

def test_extract_range():
    """Test the extract range endpoint"""
    
    url = "http://localhost:8000/api/extract/range"
    
    data = {
        "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "start_time": 152.861,
        "end_time": 210.752,
        "template_number": 0,
        "subtitles": [
            {
                "start": 152.861,
                "end": 154.279,
                "eng": "Nobody can move like Mira.",
                "kor": "춤 선이 독보적이에요"
            },
            {
                "start": 157.949,
                "end": 160.577,
                "eng": "Who else could wear a sleeping bag to the Met Gala?",
                "kor": "멧 갈라에 침낭 두르고 나오는 배짱을 보세요"
            },
            {
                "start": 190.857,
                "end": 196.154,
                "eng": "They're taking a break, and they need it, but we're gonna miss them so much!",
                "kor": "쉴 때가 되긴 했지만 너무 보고 싶을 거예요!"
            },
            {
                "start": 205.997,
                "end": 210.752,
                "eng": "All right. Looking good over there. Okay. Ready? Ready. But where are the girls?",
                "kor": "어디 보자, 저긴 된 것 같네 준비됐죠? 근데 멤버들은?"
            }
        ],
        "title_1": "KPop.Demon.Hunters.2",
        "title_2": ""
    }
    
    print("Testing Extract Range API...")
    print(f"URL: {url}")
    print(f"Media: {data['media_path']}")
    print(f"Duration: {data['end_time'] - data['start_time']:.1f} seconds")
    print(f"Subtitles: {len(data['subtitles'])} items")
    
    try:
        # Send request
        response = requests.post(url, json=data)
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print(f"\n✓ Job created successfully!")
            print(f"Job ID: {job_id}")
            print(f"Status: {result.get('status')}")
            print(f"Message: {result.get('message')}")
            
            # Poll for status
            print("\nPolling for job status...")
            for i in range(60):  # Poll for up to 60 seconds
                time.sleep(1)
                status_response = requests.get(f"http://localhost:8000/api/status/{job_id}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"[{i+1}s] Status: {status_data.get('status')} - {status_data.get('message')}")
                    
                    if status_data.get('status') == 'completed':
                        print("\n✓ Job completed successfully!")
                        print(f"Output file: {status_data.get('output_file')}")
                        break
                    elif status_data.get('status') == 'failed':
                        print("\n✗ Job failed!")
                        print(f"Error: {status_data.get('error')}")
                        break
                else:
                    print(f"Failed to get status: {status_response.status_code}")
                    
        else:
            print(f"\n✗ Request failed!")
            print(f"Response text: {response.text}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                pass
                
    except requests.exceptions.ConnectionError:
        print("\n✗ Connection failed! Is the API server running?")
        print("Start the server with: python main.py")
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_extract_range()