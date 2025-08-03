#!/usr/bin/env python3
"""
새로운 디렉토리 구조 및 파일명 테스트
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_new_output_structure():
    """새로운 출력 구조 테스트"""
    print("=== 새로운 출력 구조 테스트 ===")
    
    # Template 1 테스트
    data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "start_time": 0.0,
        "end_time": 5.0,
        "text_eng": "Test new structure with template one",
        "text_kor": "새로운 구조를 템플릿 1로 테스트",
        "note": "구조 테스트",
        "keywords": ["test", "structure"],
        "template_number": 1,
        "individual_clips": True
    }
    
    print("Template 1 요청 전송 중...")
    response = requests.post(f"{BASE_URL}/api/clip", json=data)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result["job_id"]
        print(f"Job ID: {job_id}")
        
        # 상태 확인
        print("작업 진행 상황 확인 중...")
        for i in range(30):
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"  상태: {status_data['status']} - {status_data['message']}")
                
                if status_data['status'] == 'completed':
                    print(f"\n✅ 작업 완료!")
                    print(f"출력 파일: {status_data.get('output_file', 'N/A')}")
                    
                    # 파일명 패턴 확인
                    output_file = status_data.get('output_file', '')
                    if 'tp_1.mp4' in output_file:
                        print("✅ 새로운 파일명 패턴 적용됨: YYYYMMDD_HHMMSS_tp_1.mp4")
                    else:
                        print("❌ 파일명 패턴이 예상과 다름")
                    
                    # 디렉토리 구조 확인
                    if '/2025-' in output_file:  # 날짜 패턴 확인
                        print("✅ 날짜별 디렉토리 구조 적용됨: /output/YYYY-MM-DD/job_id/")
                    else:
                        print("❌ 디렉토리 구조가 예상과 다름")
                    
                    return True
                elif status_data['status'] == 'failed':
                    print(f"❌ 작업 실패: {status_data.get('error', 'Unknown error')}")
                    return False
            
            time.sleep(1)
        
        print("⏱️ 시간 초과")
        return False
    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)
        return False

if __name__ == "__main__":
    success = test_new_output_structure()
    
    if success:
        print("\n✨ 새로운 출력 구조 테스트 성공!")
        print("✅ 파일명: YYYYMMDD_HHMMSS_tp_X.mp4")
        print("✅ 디렉토리: /output/YYYY-MM-DD/job_id/")
    else:
        print("\n❌ 테스트 실패")