#!/usr/bin/env python3
"""
템플릿 10 자막 표시 문제 테스트
"""
import requests
import json
import time
import os

# API 엔드포인트
API_URL = "http://localhost:8080/api/clip/batch"

# 테스트 데이터 - 템플릿 10 (쇼츠 원본 추출)
test_data = {
    "media_path": "/mnt/qnap/media_eng/indexed_media/Frozen.2013.1080p.BluRay.x264.YIFY.mp4",
    "template_number": 10,  # template_original_shorts
    "individual_clips": True,
    "title_1": "테스트 타이틀 1",
    "title_2": "테스트 타이틀 2",
    "clips": [
        {
            "start_time": 5.0,
            "end_time": 10.0,
            "text_eng": "This is a test sentence for subtitle display.",
            "text_kor": "이것은 자막 표시를 위한 테스트 문장입니다.",
            "keywords": ["test", "subtitle", "display"]
        }
    ]
}

def test_template_10():
    """템플릿 10 자막 표시 테스트"""
    print("=== 템플릿 10 자막 표시 테스트 ===")
    print(f"미디어: {test_data['media_path']}")
    print(f"구간: {test_data['clips'][0]['start_time']}s - {test_data['clips'][0]['end_time']}s")
    print(f"영어 자막: {test_data['clips'][0]['text_eng']}")
    print(f"한글 자막: {test_data['clips'][0]['text_kor']}")
    print()
    
    # API 요청
    try:
        response = requests.post(API_URL, json=test_data)
        response.raise_for_status()
        result = response.json()
        
        job_id = result['job_id']
        print(f"작업 ID: {job_id}")
        print(f"상태: {result['status']}")
        print(f"메시지: {result['message']}")
        print()
        
        # 작업 상태 모니터링
        status_url = f"http://localhost:8080/api/jobs/{job_id}"
        while True:
            time.sleep(2)
            status_response = requests.get(status_url)
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"진행률: {status_data.get('progress', 0)}% - {status_data.get('message', '')}")
                
                if status_data.get('status') == 'completed':
                    print("\n작업 완료!")
                    if 'outputs' in status_data:
                        for output in status_data['outputs']:
                            print(f"  - {output}")
                    break
                elif status_data.get('status') == 'error':
                    print("\n작업 실패!")
                    print(f"에러: {status_data.get('message', '')}")
                    break
            else:
                print("상태 확인 실패")
                
    except requests.exceptions.HTTPError as e:
        print(f"테스트 실패: {e}")
        if e.response.status_code == 422:
            print("상세 에러:")
            print(json.dumps(e.response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"테스트 실패: {e}")

if __name__ == "__main__":
    test_template_10()