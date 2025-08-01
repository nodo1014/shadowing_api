#!/usr/bin/env python3
"""
Clipping API 테스트 스크립트
"""

import requests
import json
import time
from pathlib import Path

# API 기본 URL
BASE_URL = "http://localhost:8080"

def test_type1_clipping():
    """Type 1 클리핑 테스트: 무자막 2회 + 영한자막 2회"""
    print("=== Type 1 클리핑 테스트 ===")
    
    # 테스트 데이터
    data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "start_time": 46.921,
        "end_time": 52.343,
        "text_eng": "The world will know you as pop stars, but you will be much more than that.",
        "text_kor": "세상은 여러분을 팝스타로 알겠지만, 여러분은 그 이상의 존재가 될 것입니다.",
        "note": "much more than: ~보다 훨씬 더",
        "keywords": ["world", "pop stars", "much more"],
        "clipping_type": 1,
        "individual_clips": True
    }
    
    # 클리핑 요청
    response = requests.post(f"{BASE_URL}/api/clip", json=data)
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"Job ID: {job_id}")
        
        # 상태 확인
        check_job_status(job_id)
        
        return job_id
    else:
        print(f"오류: {response.text}")
        return None


def test_type2_clipping():
    """Type 2 클리핑 테스트: 무자막 2회 + 블랭크 2회 + 영한자막+노트 2회"""
    print("\n=== Type 2 클리핑 테스트 ===")
    
    # 테스트 데이터
    data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "start_time": 56.0,
        "end_time": 62.0,
        "text_eng": "I need you to be ready for what's coming.",
        "text_kor": "다가올 일에 대비해야 합니다.",
        "note": "be ready for: ~에 대비하다",
        "keywords": ["ready", "coming"],
        "clipping_type": 2,
        "individual_clips": False
    }
    
    # 클리핑 요청
    response = requests.post(f"{BASE_URL}/api/clip", json=data)
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"Job ID: {job_id}")
        
        # 상태 확인
        check_job_status(job_id)
        
        return job_id
    else:
        print(f"오류: {response.text}")
        return None


def test_blank_generation():
    """블랭크 텍스트 생성 테스트"""
    print("\n=== 블랭크 텍스트 생성 테스트 ===")
    
    data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "start_time": 70.0,
        "end_time": 75.0,
        "text_eng": "Hello world, how are you today?",
        "text_kor": "안녕하세요, 오늘 어떻게 지내세요?",
        "note": "",
        "keywords": ["Hello", "world", "today"],  # 대소문자 혼합
        "clipping_type": 2,
        "individual_clips": True
    }
    
    response = requests.post(f"{BASE_URL}/api/clip", json=data)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"Job ID: {job_id}")
        print(f"원본: {data['text_eng']}")
        print(f"키워드: {data['keywords']}")
        print("예상 블랭크: _____ _____, how are you _____?")
        
        check_job_status(job_id)
        return job_id
    else:
        print(f"오류: {response.text}")
        return None


def check_job_status(job_id, max_wait=60):
    """작업 상태 확인"""
    print("\n작업 진행 상황:")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/api/status/{job_id}")
        
        if response.status_code == 200:
            status = response.json()
            print(f"  [{status['progress']}%] {status['message']}")
            
            if status['status'] == 'completed':
                print(f"\n✅ 작업 완료!")
                print(f"  출력 파일: {status['output_file']}")
                if status['individual_clips']:
                    print(f"  개별 클립: {len(status['individual_clips'])}개")
                return True
            elif status['status'] == 'failed':
                print(f"\n❌ 작업 실패: {status.get('error', 'Unknown error')}")
                return False
        
        time.sleep(1)
    
    print("\n⏱️ 시간 초과")
    return False


def download_clip(job_id):
    """클립 다운로드"""
    print(f"\n클립 다운로드: {job_id}")
    
    # 메인 클립 다운로드
    response = requests.get(f"{BASE_URL}/api/download/{job_id}")
    
    if response.status_code == 200:
        filename = f"downloaded_clip_{job_id}.mp4"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ 다운로드 완료: {filename}")
        print(f"   파일 크기: {len(response.content) / 1024 / 1024:.2f} MB")
    else:
        print(f"❌ 다운로드 실패: {response.status_code}")


def test_batch_clipping():
    """배치 클리핑 테스트"""
    print("\n=== 배치 클리핑 테스트 ===")
    
    # 배치 데이터
    data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "clips": [
            {
                "start_time": 10.0,
                "end_time": 15.0,
                "text_eng": "Welcome to the world of K-pop demon hunters.",
                "text_kor": "K-pop 악마 사냥꾼의 세계에 오신 것을 환영합니다.",
                "note": "welcome to: ~에 오신 것을 환영합니다",
                "keywords": ["Welcome", "world"]
            },
            {
                "start_time": 20.0,
                "end_time": 25.0,
                "text_eng": "Your mission is to protect the innocent.",
                "text_kor": "당신의 임무는 무고한 사람들을 보호하는 것입니다.",
                "note": "protect: 보호하다",
                "keywords": ["mission", "protect"]
            },
            {
                "start_time": 30.0,
                "end_time": 35.0,
                "text_eng": "The demons are getting stronger every day.",
                "text_kor": "악마들은 매일 더 강해지고 있습니다.",
                "note": "getting stronger: 더 강해지다",
                "keywords": ["demons", "stronger"]
            }
        ],
        "clipping_type": 2,
        "individual_clips": True
    }
    
    # 배치 클리핑 요청
    response = requests.post(f"{BASE_URL}/api/clip/batch", json=data)
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"Job ID: {job_id}")
        print(f"총 클립 수: {len(data['clips'])}")
        
        # 상태 확인
        check_batch_status(job_id)
        
        return job_id
    else:
        print(f"오류: {response.text}")
        return None


def check_batch_status(job_id, max_wait=120):
    """배치 작업 상태 확인"""
    print("\n배치 작업 진행 상황:")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/api/batch/status/{job_id}")
        
        if response.status_code == 200:
            status = response.json()
            completed = status.get('completed_clips', 0)
            total = status.get('total_clips', 0)
            
            print(f"  [{status['progress']}%] {status['message']} ({completed}/{total})")
            
            if status['status'] == 'completed':
                print(f"\n✅ 배치 작업 완료!")
                print(f"  생성된 클립: {len(status.get('output_files', []))}개")
                for file_info in status.get('output_files', []):
                    print(f"    - 클립 {file_info['clip_num']}: {file_info['start_time']:.1f}s-{file_info['end_time']:.1f}s")
                return True
            elif status['status'] == 'failed':
                print(f"\n❌ 배치 작업 실패: {status.get('error', 'Unknown error')}")
                return False
        
        time.sleep(2)
    
    print("\n⏱️ 시간 초과")
    return False


def download_batch_clip(job_id, clip_num):
    """배치 클립 다운로드"""
    print(f"\n배치 클립 다운로드: Job {job_id}, 클립 {clip_num}")
    
    response = requests.get(f"{BASE_URL}/api/batch/download/{job_id}/{clip_num}")
    
    if response.status_code == 200:
        filename = f"batch_clip_{job_id}_{clip_num:03d}.mp4"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ 다운로드 완료: {filename}")
        print(f"   파일 크기: {len(response.content) / 1024 / 1024:.2f} MB")
    else:
        print(f"❌ 다운로드 실패: {response.status_code}")


def main():
    """메인 테스트 함수"""
    print("🎬 Clipping API 테스트\n")
    
    # API 상태 확인
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            info = response.json()
            print(f"API 서비스: {info['service']}")
            print(f"버전: {info['version']}")
            print(f"상태: {info['status']}\n")
        else:
            print("❌ API 서버에 연결할 수 없습니다.")
            return
    except:
        print("❌ API 서버가 실행 중이지 않습니다.")
        print("먼저 다음 명령어로 서버를 실행하세요:")
        print("python3 clipping_api.py")
        return
    
    # 테스트 실행
    job_ids = []
    
    # Type 1 테스트
    job_id = test_type1_clipping()
    if job_id:
        job_ids.append(('single', job_id))
        time.sleep(2)
    
    # Type 2 테스트
    job_id = test_type2_clipping()
    if job_id:
        job_ids.append(('single', job_id))
        time.sleep(2)
    
    # 블랭크 생성 테스트
    job_id = test_blank_generation()
    if job_id:
        job_ids.append(('single', job_id))
        time.sleep(2)
    
    # 배치 클리핑 테스트
    job_id = test_batch_clipping()
    if job_id:
        job_ids.append(('batch', job_id))
    
    # 다운로드 테스트
    if job_ids:
        time.sleep(3)
        
        # 단일 클립 다운로드
        for job_type, job_id in job_ids:
            if job_type == 'single':
                download_clip(job_id)
                break
        
        # 배치 클립 다운로드 (첫 번째 클립)
        for job_type, job_id in job_ids:
            if job_type == 'batch':
                download_batch_clip(job_id, 1)
                break
    
    print("\n✨ 테스트 완료!")
    print(f"생성된 작업: {len(job_ids)}개 (단일: {sum(1 for t, _ in job_ids if t == 'single')}, 배치: {sum(1 for t, _ in job_ids if t == 'batch')})")


if __name__ == "__main__":
    main()