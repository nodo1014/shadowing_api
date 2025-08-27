#!/usr/bin/env python3
"""
Test script for standardized encoding options
"""
import subprocess
import tempfile
import os
import json
from pathlib import Path
from template_standards import TemplateStandards
from template_video_encoder import TemplateVideoEncoder

def check_video_properties(video_path: str) -> dict:
    """비디오 파일의 속성을 확인"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,pix_fmt',
        '-print_format', 'json',
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get('streams', [{}])[0]
    return {}

def check_audio_properties(video_path: str) -> dict:
    """오디오 파일의 속성을 확인"""
    cmd = [
        'ffprobe', '-v', 'error', 
        '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_name,sample_rate,channels,bit_rate',
        '-print_format', 'json',
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get('streams', [{}])[0]
    return {}

def test_encoding_standards():
    """인코딩 표준이 제대로 적용되는지 테스트"""
    
    print("=== Testing Encoding Standards ===")
    print(f"Expected CRF: {TemplateStandards.STANDARD_VIDEO_CRF}")
    print(f"Expected Audio Sample Rate: {TemplateStandards.OUTPUT_SAMPLE_RATE}")
    print(f"Expected Audio Codec: {TemplateStandards.OUTPUT_AUDIO_CODEC}")
    print()
    
    # 테스트용 비디오 생성
    test_media = "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-%5BYTS.MX%5D.mp4"
    
    # 간단한 템플릿 테스트
    encoder = TemplateVideoEncoder()
    
    subtitle_data = {
        'start_time': 0,
        'end_time': 5,
        'english': 'Test subtitle',
        'korean': '테스트 자막',
        'eng': 'Test subtitle',
        'kor': '테스트 자막'
    }
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        # Template 1으로 비디오 생성
        success = encoder.create_from_template(
            template_name="template_1",
            media_path=test_media,
            subtitle_data=subtitle_data,
            output_path=output_path,
            start_time=10.0,
            end_time=15.0,
            save_individual_clips=False
        )
        
        if success and os.path.exists(output_path):
            print(f"✓ Video created successfully: {output_path}")
            
            # 비디오 속성 확인
            video_props = check_video_properties(output_path)
            print("\nVideo Properties:")
            print(f"  Codec: {video_props.get('codec_name', 'N/A')}")
            print(f"  Size: {video_props.get('width', 'N/A')}x{video_props.get('height', 'N/A')}")
            print(f"  Pixel Format: {video_props.get('pix_fmt', 'N/A')}")
            
            # 오디오 속성 확인
            audio_props = check_audio_properties(output_path)
            print("\nAudio Properties:")
            print(f"  Codec: {audio_props.get('codec_name', 'N/A')}")
            print(f"  Sample Rate: {audio_props.get('sample_rate', 'N/A')}")
            print(f"  Channels: {audio_props.get('channels', 'N/A')}")
            
            # 검증
            print("\n=== Validation ===")
            if audio_props.get('sample_rate') == str(TemplateStandards.OUTPUT_SAMPLE_RATE):
                print(f"✓ Audio sample rate is correct: {TemplateStandards.OUTPUT_SAMPLE_RATE}Hz")
            else:
                print(f"✗ Audio sample rate mismatch: expected {TemplateStandards.OUTPUT_SAMPLE_RATE}, got {audio_props.get('sample_rate')}")
            
            if audio_props.get('codec_name') == TemplateStandards.OUTPUT_AUDIO_CODEC:
                print(f"✓ Audio codec is correct: {TemplateStandards.OUTPUT_AUDIO_CODEC}")
            else:
                print(f"✗ Audio codec mismatch: expected {TemplateStandards.OUTPUT_AUDIO_CODEC}, got {audio_props.get('codec_name')}")
                
        else:
            print("✗ Failed to create video")
            
    finally:
        # Cleanup
        if os.path.exists(output_path):
            os.unlink(output_path)
            print(f"\nCleaned up test file: {output_path}")

def test_mixed_template_encoding():
    """Mixed template에서 인코딩 표준 테스트"""
    import requests
    import time
    
    print("\n=== Testing Mixed Template Encoding ===")
    
    # API 서버가 실행 중인지 확인
    try:
        response = requests.get("http://localhost:8080/health")
        if response.status_code != 200:
            print("API server is not running. Please start it first.")
            return
    except:
        print("API server is not running. Please start it first.")
        return
    
    # Mixed template 요청
    request_data = {
        "media_path": "/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-%5BYTS.MX%5D.mp4",
        "clips": [
            {
                "template_number": 0,
                "start_time": 29.821,
                "end_time": 46.838,
                "subtitles": [
                    {
                        "start": 30.322,
                        "end": 32.574,
                        "eng": "The world will know you as pop stars,",
                        "kor": "세상은 너희를 팝 스타로 알겠지만"
                    }
                ]
            },
            {
                "template_number": 1,
                "start_time": 46.921,
                "end_time": 52.343,
                "text_eng": "The world will know you as pop stars, but you will be much more than that.",
                "text_kor": "세상은 너희를 팝 스타로 알겠지만, 너희는 그 이상의 존재가 될 거야."
            }
        ],
        "combine": True,
        "individual_clips": False
    }
    
    response = requests.post("http://localhost:8080/api/clip/mixed", json=request_data)
    
    if response.status_code == 200:
        job_data = response.json()
        job_id = job_data['job_id']
        print(f"Job started: {job_id}")
        
        # 작업 완료 대기
        max_attempts = 30
        for i in range(max_attempts):
            time.sleep(2)
            status_response = requests.get(f"http://localhost:8080/api/job/{job_id}/status")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"Status: {status['status']} - {status.get('progress', 0)}%")
                
                if status['status'] == 'completed':
                    print("✓ Job completed successfully")
                    
                    # 결합된 파일 확인
                    if status.get('combined_file'):
                        combined_path = Path("/home/kang/dev_amd/shadowing_maker_xls/output") / status['combined_file']
                        if combined_path.exists():
                            print(f"\nChecking combined file: {combined_path}")
                            
                            # 속성 확인
                            video_props = check_video_properties(str(combined_path))
                            audio_props = check_audio_properties(str(combined_path))
                            
                            print(f"Video codec: {video_props.get('codec_name')}")
                            print(f"Audio codec: {audio_props.get('codec_name')}")
                            print(f"Audio sample rate: {audio_props.get('sample_rate')}")
                            
                    break
                elif status['status'] == 'failed':
                    print(f"✗ Job failed: {status.get('error')}")
                    break
    else:
        print(f"Failed to start job: {response.status_code}")

if __name__ == "__main__":
    # 기본 인코딩 테스트
    test_encoding_standards()
    
    # Mixed template 테스트
    test_mixed_template_encoding()