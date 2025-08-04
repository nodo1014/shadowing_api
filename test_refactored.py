#!/usr/bin/env python3
"""
Test script for refactored modules
"""
import sys
from pathlib import Path

def test_imports():
    """Test if all modules can be imported"""
    print("Testing module imports...")
    
    try:
        # Test database adapter
        from database_adapter import init_db, save_job_to_db, get_job_by_id
        print("✓ Database adapter imported successfully")
        
        # Test video encoder adapter
        from video_encoder_adapter import VideoEncoder, TemplateVideoEncoder
        print("✓ Video encoder adapter imported successfully")
        
        # Test core modules
        from shadowing_maker.core.video.ffmpeg_utils import run_ffmpeg_command
        print("✓ FFmpeg utils imported successfully")
        
        from shadowing_maker.core.video.encoder import VideoEncoder as BaseEncoder
        print("✓ Base encoder imported successfully")
        
        from shadowing_maker.core.subtitle.generator import SubtitleGenerator
        print("✓ Subtitle generator imported successfully")
        
        # Test database modules
        from shadowing_maker.database.connection import get_db_connection
        print("✓ Database connection imported successfully")
        
        from shadowing_maker.database.repositories.job_repo import JobRepository
        print("✓ Job repository imported successfully")
        
        # Test API modules
        from shadowing_maker.api.app import app
        print("✓ FastAPI app imported successfully")
        
        print("\n✅ All modules imported successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test database operations"""
    print("\nTesting database operations...")
    
    try:
        from database_adapter import init_db, save_job_to_db, get_job_by_id, delete_job
        import uuid
        
        # Initialize database
        init_db()
        print("✓ Database initialized")
        
        # Create test job
        test_id = str(uuid.uuid4())
        job_data = {
            "id": test_id,
            "type": "test",
            "status": "pending",
            "media_path": "/test/path.mp4",
            "text_eng": "Test English",
            "text_kor": "테스트 한국어"
        }
        
        save_job_to_db(job_data)
        print(f"✓ Test job created: {test_id}")
        
        # Retrieve job
        retrieved_job = get_job_by_id(test_id)
        if retrieved_job and retrieved_job['id'] == test_id:
            print("✓ Job retrieved successfully")
        else:
            print("❌ Failed to retrieve job")
        
        # Delete job
        if delete_job(test_id):
            print("✓ Job deleted successfully")
        else:
            print("❌ Failed to delete job")
        
        print("\n✅ Database operations successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Database test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_video_encoder():
    """Test video encoder"""
    print("\nTesting video encoder...")
    
    try:
        from video_encoder_adapter import VideoEncoder, TemplateVideoEncoder
        
        # Test VideoEncoder
        encoder = VideoEncoder()
        encoder.set_pattern(1, 0, 3)
        print("✓ VideoEncoder created and pattern set")
        
        # Test TemplateVideoEncoder
        template_encoder = TemplateVideoEncoder()
        templates = template_encoder.templates
        print(f"✓ TemplateVideoEncoder created with {len(templates)} templates")
        
        # List available templates
        for name, template in templates.items():
            print(f"  - {name}: {template['name']}")
        
        print("\n✅ Video encoder test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Video encoder test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Test API endpoints"""
    print("\nTesting API endpoints...")
    
    try:
        from shadowing_maker.api.app import app
        
        # Check registered routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"✓ API app has {len(routes)} routes registered")
        
        # Check key endpoints
        key_endpoints = [
            '/api/health',
            '/api/clip/create',
            '/api/batch/create',
            '/api/job/{job_id}',
            '/api/admin/statistics'
        ]
        
        for endpoint in key_endpoints:
            if any(endpoint in route for route in routes):
                print(f"  ✓ {endpoint}")
            else:
                print(f"  ❌ {endpoint} not found")
        
        print("\n✅ API endpoints test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ API test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*50)
    print("REFACTORED MODULE TEST SUITE")
    print("="*50)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Database", test_database()))
    results.append(("Video Encoder", test_video_encoder()))
    results.append(("API Endpoints", test_api_endpoints()))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Refactoring successful!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())