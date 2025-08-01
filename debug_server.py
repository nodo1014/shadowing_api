#!/usr/bin/env python3
"""
Debug script to test the clipping API and identify server shutdown issues
"""

import requests
import json
import time
import sys

API_BASE = "http://localhost:8080"

def test_api_endpoints():
    """Test various API endpoints to identify issues"""
    
    print("=== Testing API Endpoints ===")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{API_BASE}/api")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False
    
    # Test 2: Test invalid job status lookup
    try:
        response = requests.get(f"{API_BASE}/api/status/invalid-job-id")
        print(f"Invalid job status: {response.status_code}")
        if response.status_code != 404:
            print(f"Expected 404, got {response.status_code}")
    except Exception as e:
        print(f"Invalid job status test failed: {e}")
    
    # Test 3: Create a test clip job (without actually processing)
    test_data = {
        "media_path": "/home/kang/dev_amd/shadowing_maker_xls/media/test_video.mp4",
        "start_time": 10.0,
        "end_time": 15.0,
        "text_eng": "Test clip",
        "text_kor": "테스트 클립",
        "note": "Debug test",
        "keywords": ["test"],
        "clipping_type": 1,
        "individual_clips": False
    }
    
    try:
        print(f"Sending POST request with data: {json.dumps(test_data, indent=2)}")
        response = requests.post(f"{API_BASE}/api/clip", json=test_data)
        print(f"Create clip: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            job_id = result["job_id"]
            print(f"Job created: {job_id}")
            
            # Test status checking multiple times
            for i in range(5):
                time.sleep(1)
                try:
                    status_response = requests.get(f"{API_BASE}/api/status/{job_id}")
                    print(f"Status check {i+1}: {status_response.status_code}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"  Status: {status_data['status']}, Progress: {status_data['progress']}")
                    else:
                        print(f"  Error: {status_response.text}")
                        break
                except Exception as e:
                    print(f"Status check {i+1} failed: {e}")
                    break
        else:
            print(f"Error creating clip: {response.text}")
            
    except Exception as e:
        print(f"Create clip test failed: {e}")
    
    return True

def monitor_server_health():
    """Monitor server health during operations"""
    print("\n=== Monitoring Server Health ===")
    
    for i in range(10):
        try:
            response = requests.get(f"{API_BASE}/api", timeout=5)
            print(f"Health check {i+1}: {response.status_code}")
            time.sleep(2)
        except Exception as e:
            print(f"Health check {i+1} failed: {e}")
            break

if __name__ == "__main__":
    print("Starting API debug tests...")
    
    if test_api_endpoints():
        monitor_server_health()
    
    print("Debug tests completed.")