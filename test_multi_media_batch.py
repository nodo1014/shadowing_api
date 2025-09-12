#!/usr/bin/env python3
"""
다중 미디어 배치 API 테스트
"""
import requests
import json
import time
from typing import Dict, List

# API 서버 설정
API_BASE_URL = "http://localhost:8000/api"

def test_multi_media_batch():
    """다중 미디어 배치 클리핑 테스트"""
    
    # 테스트용 미디어 경로들 (실제 경로로 변경 필요)
    test_clips = [
        {
            "media_path": "/mnt/ssd1t/shadowing/Emily.in.Paris.S01E01.1080p.WEB.H264-CAKES.mkv",
            "start_time": 10,
            "end_time": 15,
            "text_eng": "I love Paris",
            "text_kor": "파리가 좋아요",
            "note": "에밀리가 파리 도착",
            "keywords": ["love", "Paris"]
        },
        {
            "media_path": "/mnt/ssd1t/shadowing/Emily.in.Paris.S01E02.1080p.WEB.H264-CAKES.mkv", 
            "start_time": 20,
            "end_time": 25,
            "text_eng": "This is amazing",
            "text_kor": "정말 놀라워요",
            "note": "첫 출근",
            "keywords": ["amazing"]
        },
        {
            "media_path": "/mnt/ssd1t/shadowing/Emily.in.Paris.S01E03.1080p.WEB.H264-CAKES.mkv",
            "start_time": 30,
            "end_time": 35,
            "text_eng": "Let's work together",
            "text_kor": "함께 일해요",
            "note": "동료와 대화",
            "keywords": ["work", "together"]
        }
    ]
    
    # 1. 일반 템플릿으로 테스트 (템플릿 1)
    print("=== 다중 미디어 배치 테스트 (템플릿 1) ===")
    request_data = {
        "clips": test_clips,
        "template_number": 1,
        "individual_clips": True,
        "title_1": "Emily in Paris",
        "title_2": "Best Moments"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/clip/batch-multi",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        job_id = result.get("job_id")
        print(f"✅ 작업 시작됨: {job_id}")
        print(f"메시지: {result.get('message')}")
        
        # 작업 상태 확인
        check_job_status(job_id)
    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)
    
    print("\n" + "="*50 + "\n")
    
    # 2. 쇼츠 템플릿으로 테스트 (템플릿 11)
    print("=== 다중 미디어 배치 테스트 (쇼츠 템플릿 11) ===")
    request_data["template_number"] = 11
    request_data["title_1"] = "에밀리 인 파리"
    request_data["title_2"] = "명장면 모음"
    
    response = requests.post(
        f"{API_BASE_URL}/clip/batch-multi",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        job_id = result.get("job_id")
        print(f"✅ 작업 시작됨: {job_id}")
        print(f"메시지: {result.get('message')}")
        
        # 작업 상태 확인
        check_job_status(job_id)
    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)


def check_job_status(job_id: str, max_wait: int = 60):
    """작업 상태 확인"""
    print(f"\n작업 진행 상황 확인 중...")
    
    for i in range(max_wait):
        response = requests.get(f"{API_BASE_URL}/job/{job_id}")
        
        if response.status_code == 200:
            status = response.json()
            progress = status.get("progress", 0)
            message = status.get("message", "")
            job_status = status.get("status", "unknown")
            
            print(f"\r[{progress:3d}%] {job_status}: {message}", end="")
            
            if job_status == "completed":
                print("\n✅ 작업 완료!")
                output_files = status.get("output_files", [])
                if output_files:
                    print(f"\n생성된 파일 ({len(output_files)}개):")
                    for file_info in output_files:
                        print(f"  - Clip {file_info['clip_number']}: {file_info['file']}")
                break
            elif job_status == "failed":
                print(f"\n❌ 작업 실패: {status.get('error_message', 'Unknown error')}")
                break
        else:
            print(f"\n⚠️ 상태 확인 실패: {response.status_code}")
            break
        
        time.sleep(1)


def test_mixed_media_single_batch():
    """단일/다중 미디어 혼합 테스트"""
    print("=== 단일/다중 미디어 혼합 테스트 ===")
    
    # 기존 배치 API로 다중 미디어 지원 테스트
    test_clips = [
        {
            # media_path 지정 - 다중 미디어 모드
            "media_path": "/mnt/ssd1t/shadowing/Emily.in.Paris.S01E01.1080p.WEB.H264-CAKES.mkv",
            "start_time": 100,
            "end_time": 105,
            "text_eng": "Hello from episode 1",
            "text_kor": "에피소드 1에서 안녕",
            "keywords": ["Hello"]
        },
        {
            # media_path 지정 - 다중 미디어 모드  
            "media_path": "/mnt/ssd1t/shadowing/Emily.in.Paris.S01E02.1080p.WEB.H264-CAKES.mkv",
            "start_time": 200,
            "end_time": 205,
            "text_eng": "Hello from episode 2",
            "text_kor": "에피소드 2에서 안녕",
            "keywords": ["Hello"]
        }
    ]
    
    request_data = {
        # media_path를 지정하지 않음 - 각 클립의 media_path 사용
        "clips": test_clips,
        "template_number": 2,  # Keyword Focus 템플릿
        "individual_clips": True
    }
    
    response = requests.post(
        f"{API_BASE_URL}/clip/batch",  # 기존 배치 API 사용
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        job_id = result.get("job_id")
        print(f"✅ 작업 시작됨: {job_id}")
        check_job_status(job_id)
    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    print("다중 미디어 배치 API 테스트 시작\n")
    
    # 1. 새로운 multi-media 엔드포인트 테스트
    test_multi_media_batch()
    
    print("\n" + "="*70 + "\n")
    
    # 2. 기존 배치 API의 다중 미디어 지원 테스트
    test_mixed_media_single_batch()
    
    print("\n테스트 완료!")