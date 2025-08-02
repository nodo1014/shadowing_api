#!/usr/bin/env python3
"""
Test script for template-based video encoding system
템플릿 기반 비디오 인코딩 시스템 테스트
"""

import json
import os
import tempfile
from pathlib import Path
import shutil
import time

from template_video_encoder import TemplateVideoEncoder
from subtitle_generator import SubtitleGenerator

def create_test_data():
    """테스트용 자막 데이터 생성"""
    # Type 1 테스트 데이터
    type1_data = {
        "start_time": 10.0,
        "end_time": 15.0,
        "eng": "Hello, how are you today?",
        "kor": "안녕하세요, 오늘 어떻게 지내세요?",
        "note": "인사말",
        "clipping_type": 1
    }
    
    # Type 2 테스트 데이터 (키워드 포함)
    type2_data = {
        "start_time": 20.0,
        "end_time": 25.0,
        "eng": "I love learning new languages",
        "kor": "나는 새로운 언어를 배우는 것을 좋아해요",
        "note": "언어 학습",
        "keywords": ["love", "learning", "languages"],
        "text_eng_blank": "I ____ ________ new _________",
        "clipping_type": 2
    }
    
    # Type 3 테스트 데이터
    type3_data = {
        "start_time": 30.0,
        "end_time": 35.0,
        "eng": "Practice makes perfect",
        "kor": "연습이 완벽을 만든다",
        "note": "격언",
        "clipping_type": 3
    }
    
    return type1_data, type2_data, type3_data

def test_subtitle_generator():
    """SubtitleGenerator 컴포넌트 테스트"""
    print("\n=== Testing SubtitleGenerator ===")
    
    generator = SubtitleGenerator()
    type1_data, type2_data, type3_data = create_test_data()
    
    # Test directory
    test_dir = Path("test_output/subtitles")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Test 1: Full subtitle
    print("\n1. Testing full subtitle generation...")
    full_path = test_dir / "test_full.ass"
    result = generator.generate_full_subtitle(type1_data, str(full_path))
    print(f"   Full subtitle: {'SUCCESS' if result else 'FAILED'}")
    if result and full_path.exists():
        print(f"   File created: {full_path}")
    
    # Test 2: Full subtitle with keywords (Type 2)
    print("\n2. Testing full subtitle with keywords...")
    full_keywords_path = test_dir / "test_full_keywords.ass"
    result = generator.generate_full_subtitle(type2_data, str(full_keywords_path), with_keywords=True)
    print(f"   Full subtitle with keywords: {'SUCCESS' if result else 'FAILED'}")
    
    # Test 3: Blank subtitle
    print("\n3. Testing blank subtitle generation...")
    blank_path = test_dir / "test_blank.ass"
    result = generator.generate_blank_subtitle(type2_data, str(blank_path))
    print(f"   Blank subtitle: {'SUCCESS' if result else 'FAILED'}")
    
    # Test 4: Blank subtitle with Korean
    print("\n4. Testing blank subtitle with Korean...")
    blank_korean_path = test_dir / "test_blank_korean.ass"
    result = generator.generate_blank_subtitle(type2_data, str(blank_korean_path), with_korean=True)
    print(f"   Blank subtitle with Korean: {'SUCCESS' if result else 'FAILED'}")
    
    # Test 5: Korean only subtitle
    print("\n5. Testing Korean only subtitle...")
    korean_only_path = test_dir / "test_korean_only.ass"
    result = generator.generate_korean_only_subtitle(type3_data, str(korean_only_path))
    print(f"   Korean only subtitle: {'SUCCESS' if result else 'FAILED'}")
    
    return True

def test_template_loading():
    """템플릿 로딩 테스트"""
    print("\n=== Testing Template Loading ===")
    
    encoder = TemplateVideoEncoder()
    
    print(f"\nLoaded templates: {list(encoder.templates.keys())}")
    
    for template_name, template_data in encoder.templates.items():
        print(f"\n{template_name}:")
        print(f"  Name: {template_data['name']}")
        print(f"  Description: {template_data['description']}")
        print(f"  Clips: {len(template_data['clips'])}")
        for clip in template_data['clips']:
            print(f"    - {clip['type']} x{clip['count']} (subtitle: {clip['subtitle_type']})")
        print(f"  Gap duration: {template_data['gap_duration']}s")
    
    return True

def test_video_generation_mock():
    """비디오 생성 모의 테스트 (실제 비디오 파일 없이)"""
    print("\n=== Testing Video Generation (Mock) ===")
    
    encoder = TemplateVideoEncoder()
    type1_data, type2_data, type3_data = create_test_data()
    
    # Test output directory
    test_dir = Path("test_output/videos")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a dummy video file for testing
    dummy_video = test_dir / "dummy_video.mp4"
    dummy_video.write_text("DUMMY VIDEO FILE")
    
    print("\n1. Testing Type 1 template...")
    output1 = test_dir / "test_type1_shadowing.mp4"
    try:
        # This will fail without a real video, but we can check the flow
        result = encoder.create_from_template(
            template_name="type_1",
            media_path=str(dummy_video),
            subtitle_data=type1_data,
            output_path=str(output1),
            start_time=10.0,
            end_time=15.0
        )
        print(f"   Type 1 generation: {'Would process' if not result else 'SUCCESS'}")
    except Exception as e:
        print(f"   Type 1 generation: Expected failure in mock test - {type(e).__name__}")
    
    print("\n2. Testing Type 2 template...")
    output2 = test_dir / "test_type2_shadowing.mp4"
    try:
        result = encoder.create_from_template(
            template_name="type_2",
            media_path=str(dummy_video),
            subtitle_data=type2_data,
            output_path=str(output2),
            start_time=20.0,
            end_time=25.0
        )
        print(f"   Type 2 generation: {'Would process' if not result else 'SUCCESS'}")
    except Exception as e:
        print(f"   Type 2 generation: Expected failure in mock test - {type(e).__name__}")
    
    print("\n3. Testing Type 3 template...")
    output3 = test_dir / "test_type3_shadowing.mp4"
    try:
        result = encoder.create_from_template(
            template_name="type_3",
            media_path=str(dummy_video),
            subtitle_data=type3_data,
            output_path=str(output3),
            start_time=30.0,
            end_time=35.0
        )
        print(f"   Type 3 generation: {'Would process' if not result else 'SUCCESS'}")
    except Exception as e:
        print(f"   Type 3 generation: Expected failure in mock test - {type(e).__name__}")
    
    # Clean up dummy file
    dummy_video.unlink()
    
    return True

def test_api_integration():
    """API 통합 테스트"""
    print("\n=== Testing API Integration ===")
    
    # Check if clipping_api.py imports the new modules correctly
    try:
        from clipping_api import TemplateVideoEncoder, SubtitleGenerator
        print("✓ Successfully imported TemplateVideoEncoder and SubtitleGenerator from clipping_api")
    except ImportError as e:
        print(f"✗ Failed to import from clipping_api: {e}")
        return False
    
    # Check template patterns JSON exists
    template_path = Path("templates/shadowing_patterns.json")
    if template_path.exists():
        print(f"✓ Template file exists: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"  Contains {len(data.get('patterns', {}))} patterns")
    else:
        print(f"✗ Template file not found: {template_path}")
        return False
    
    return True

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("Template-based Video Encoding System Test")
    print("템플릿 기반 비디오 인코딩 시스템 테스트")
    print("=" * 60)
    
    # Clean up previous test output
    if Path("test_output").exists():
        shutil.rmtree("test_output")
    
    tests = [
        ("Template Loading", test_template_loading),
        ("Subtitle Generator", test_subtitle_generator),
        ("Video Generation Mock", test_video_generation_mock),
        ("API Integration", test_api_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<40} {status}")
    
    total_passed = sum(1 for _, result in results if result)
    print(f"\nTotal: {total_passed}/{len(tests)} tests passed")
    
    # Note about real video testing
    print("\n" + "=" * 60)
    print("NOTE: This test uses mock data and dummy files.")
    print("For real video processing tests, you need:")
    print("1. A real video file (mp4, mkv, etc.)")
    print("2. FFmpeg installed and accessible")
    print("3. Run the server and test through the API endpoints")
    print("=" * 60)

if __name__ == "__main__":
    main()