#!/usr/bin/env python3
"""
Check job details from the API
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8080"

def check_job(job_id):
    """Check detailed job information"""
    response = requests.get(f"{BASE_URL}/api/status/{job_id}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nJob ID: {job_id}")
        print(f"Status: {data.get('status')}")
        print(f"Progress: {data.get('progress')}")
        
        # Check result field
        result = data.get('result')
        if result:
            print(f"Result type: {type(result)}")
            print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print("No result field")
            
        # Print full response
        print("\nFull response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"Failed to get job status: {response.status_code}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        job_id = sys.argv[1]
    else:
        # Use the last job ID from test
        job_id = "feeb0f68-662c-4044-b99e-52159cc5e6be"
    
    check_job(job_id)