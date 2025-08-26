#!/usr/bin/env python3
"""
Mixed Template API 테스트 스크립트
"""
import requests
import json
import time
import sys

# API 엔드포인트
BASE_URL = "http://localhost:8080"

def test_mixed_template():
    """혼합 템플릿 테스트"""
    
    # 테스트용 미디어 경로 (실제 존재하는 파일로 변경 필요)
    media_path = "/mnt/qnap/media_eng/indexed_media/22.Jump.Street.2014.1080p.BluRay.x264.YIFY.mp4"
    
    # 혼합 템플릿 요청 데이터
    request_data = {
        "media_path": media_path,
        "clips": [
            {
                "start_time": 100.0,
                "end_time": 105.0,
                "text_eng": "Hello, how are you?",
                "text_kor": "안녕하세요, 어떻게 지내세요?",
                "template_number": 1  # 기본 템플릿
            },
            {
                "start_time": 110.0,
                "end_time": 115.0,
                "text_eng": "I don't know what to say",
                "text_kor": "뭐라고 말해야 할지 모르겠어요",
                "template_number": 2,  # 키워드 블랭크
                "keywords": ["don't", "know"]
            },
            {
                "start_time": 120.0,
                "end_time": 125.0,
                "text_eng": "Thank you very much",
                "text_kor": "정말 감사합니다",
                "template_number": 3  # 점진적 학습
            }
        ],
        "combine": True,  # 하나로 결합
        "title_1": "Mixed Template Test",
        "title_2": "혼합 템플릿 테스트",
        "transitions": False
    }
    
    print("=== Mixed Template Test ===")
    print(f"Media: {media_path}")
    print(f"Clips: {len(request_data['clips'])}")
    for i, clip in enumerate(request_data['clips']):
        print(f"  Clip {i+1}: Template {clip['template_number']} - {clip['text_eng'][:30]}...")
    print(f"Combine: {request_data['combine']}")
    print()
    
    # API 호출
    try:
        print("Sending request to /api/clip/mixed...")
        response = requests.post(
            f"{BASE_URL}/api/clip/mixed",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('job_id')
            print(f"✓ Job created: {job_id}")
            print(f"  Message: {result.get('message')}")
            
            # 작업 상태 모니터링
            print("\nMonitoring job status...")
            while True:
                status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
                if status_response.status_code == 200:
                    status = status_response.json()
                    progress = status.get('progress', 0)
                    message = status.get('message', '')
                    job_status = status.get('status', '')
                    
                    print(f"\r[{progress:3d}%] {message:<50}", end='', flush=True)
                    
                    if job_status == 'completed':
                        print("\n✓ Job completed!")
                        print(f"  Output files: {len(status.get('output_files', []))}")
                        if status.get('combined_file'):
                            print(f"  Combined file: {status['combined_file']}")
                        for file_info in status.get('output_files', []):
                            print(f"    - Clip {file_info['clip_number']}: Template {file_info['template']}")
                        break
                    elif job_status == 'failed':
                        print(f"\n✗ Job failed: {status.get('error', 'Unknown error')}")
                        break
                
                time.sleep(2)
                
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"  Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API server at", BASE_URL)
        print("  Make sure the server is running: ./start_production.sh")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


def test_mixed_individual():
    """개별 파일로 생성하는 테스트"""
    print("\n=== Mixed Template Test (Individual Files) ===")
    
    media_path = "/mnt/qnap/media_eng/indexed_media/22.Jump.Street.2014.1080p.BluRay.x264.YIFY.mp4"
    
    request_data = {
        "media_path": media_path,
        "clips": [
            {
                "start_time": 200.0,
                "end_time": 203.0,
                "text_eng": "First clip",
                "text_kor": "첫 번째 클립",
                "template_number": 1
            },
            {
                "start_time": 205.0,
                "end_time": 208.0,
                "text_eng": "Second clip",
                "text_kor": "두 번째 클립",
                "template_number": 2,
                "keywords": ["Second"]
            }
        ],
        "combine": False  # 개별 파일로 생성
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/clip/mixed", json=request_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Job created: {result['job_id']}")
            # 상태 확인은 생략 (위와 동일)
        else:
            print(f"✗ Request failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


if __name__ == "__main__":
    # 서버 연결 확인
    try:
        health = requests.get(f"{BASE_URL}/health")
        if health.status_code == 200:
            print("✓ API server is running\n")
        else:
            print("✗ API server health check failed")
            sys.exit(1)
    except:
        print("✗ Cannot connect to API server")
        print("  Run: ./start_production.sh")
        sys.exit(1)
    
    # 테스트 실행
    test_mixed_template()
    test_mixed_individual()