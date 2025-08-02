#!/usr/bin/env python3
"""
Test API endpoints with the new template-based system
템플릿 기반 시스템으로 API 엔드포인트 테스트
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_single_clip_type1():
    """Test Type 1 clip generation"""
    print("\n=== Testing Type 1 Single Clip ===")
    
    payload = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/simple_test.mp4",
        "start_time": 2.0,
        "end_time": 5.0,
        "text_eng": "This is a test subtitle for Type 1",
        "text_kor": "이것은 타입 1을 위한 테스트 자막입니다",
        "note": "테스트 노트",
        "template_number": 1
    }
    
    response = requests.post(f"{BASE_URL}/api/clip", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        job_id = response.json()["job_id"]
        
        # Poll for status
        for i in range(30):  # Wait up to 30 seconds
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            if status_response.status_code == 200:
                job_data = status_response.json()
                status = job_data.get("status", "unknown")
                print(f"Job status: {status}")
                
                if status == "completed":
                    print("✓ Type 1 clip completed successfully")
                    output_file = job_data.get('output_file', 'N/A')
                    print(f"Output: {output_file}")
                    individual_clips = job_data.get('individual_clips', [])
                    if individual_clips:
                        print(f"Individual clips: {len(individual_clips)}")
                    break
                elif status == "failed":
                    print("✗ Type 1 clip failed")
                    print(f"Error: {job_data.get('error', 'Unknown error')}")
                    break
            else:
                print(f"Failed to get job status: {status_response.status_code}")
                break
            
            time.sleep(1)

def test_single_clip_type2():
    """Test Type 2 clip generation with keywords"""
    print("\n=== Testing Type 2 Single Clip ===")
    
    payload = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/simple_test.mp4",
        "start_time": 5.0,
        "end_time": 8.0,
        "text_eng": "I love learning new languages every day",
        "text_kor": "나는 매일 새로운 언어를 배우는 것을 좋아해요",
        "note": "언어 학습",
        "keywords": ["love", "learning", "languages"],
        "template_number": 2
    }
    
    response = requests.post(f"{BASE_URL}/api/clip", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        job_id = response.json()["job_id"]
        
        # Poll for status
        for i in range(30):
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            if status_response.status_code == 200:
                job_data = status_response.json()
                status = job_data.get("status", "unknown")
                print(f"Job status: {status}")
                
                if status == "completed":
                    print("✓ Type 2 clip completed successfully")
                    output_file = job_data.get('output_file', 'N/A')
                    print(f"Output: {output_file}")
                    individual_clips = job_data.get('individual_clips', [])
                    if individual_clips:
                        print(f"Individual clips: {len(individual_clips)}")
                    break
                elif status == "failed":
                    print("✗ Type 2 clip failed")
                    print(f"Error: {job_data.get('error', 'Unknown error')}")
                    break
            else:
                print(f"Failed to get job status: {status_response.status_code}")
                break
            
            time.sleep(1)

def test_batch_processing():
    """Test batch processing with mixed types"""
    print("\n=== Testing Batch Processing ===")
    
    payload = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/simple_test.mp4",
        "clips": [
            {
                "start_time": 1.0,
                "end_time": 3.0,
                "text_eng": "First subtitle for batch test",
                "text_kor": "배치 테스트를 위한 첫 번째 자막",
                "note": "배치 1"
            },
            {
                "start_time": 4.0,
                "end_time": 6.0,
                "text_eng": "Second subtitle with keywords test",
                "text_kor": "키워드가 있는 두 번째 자막 테스트",
                "note": "배치 2",
                "keywords": ["keywords", "test"]
            }
        ],
        "template_number": 2,
        "individual_clips": True
    }
    
    response = requests.post(f"{BASE_URL}/api/clip/batch", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        job_id = response.json()["job_id"]
        
        # Poll for status
        for i in range(60):  # Wait up to 60 seconds for batch
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            if status_response.status_code == 200:
                job_data = status_response.json()
                status = job_data.get("status", "unknown")
                progress = job_data.get("progress", {})
                
                if isinstance(progress, dict) and progress:
                    print(f"Job status: {status} - Progress: {progress.get('current', 0)}/{progress.get('total', 0)}")
                else:
                    print(f"Job status: {status}")
                
                if status == "completed":
                    print("✓ Batch processing completed successfully")
                    result = job_data.get('result', {})
                    print(f"Created {len(result.get('created_files', []))} files")
                    for file in result.get('created_files', []):
                        print(f"  - {file}")
                    break
                elif status == "failed":
                    print("✗ Batch processing failed")
                    print(f"Error: {job_data.get('error', 'Unknown error')}")
                    break
            else:
                print(f"Failed to get job status: {status_response.status_code}")
                break
            
            time.sleep(2)

def main():
    """Run all tests"""
    print("=" * 60)
    print("API Endpoint Tests - Template-based System")
    print("템플릿 기반 시스템 API 엔드포인트 테스트")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code != 200:
            print("✗ Server is not responding properly")
            return
        print("✓ Server is running")
    except:
        print("✗ Cannot connect to server at", BASE_URL)
        print("Make sure the server is running with ./start_production.sh")
        return
    
    # Run tests
    tests = [
        ("Type 1 Single Clip", test_single_clip_type1),
        ("Type 2 Single Clip", test_single_clip_type2),
        ("Batch Processing", test_batch_processing)
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\n✗ {test_name} failed with error: {e}")
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()