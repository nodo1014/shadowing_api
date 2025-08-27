#!/usr/bin/env python3
"""
ASS 파일 생성 테스트 - styles.py 설정이 적용되는지 확인
"""
from ass_generator import ASSGenerator
from api.routes.extract import create_multi_subtitle_file
from api.models import SubtitleInfo
from pathlib import Path
import os

def test_ass_generator():
    """ASSGenerator를 직접 사용하여 테스트"""
    print("=" * 60)
    print("Testing ASSGenerator directly")
    print("=" * 60)
    
    generator = ASSGenerator()
    
    # 테스트 자막 데이터
    test_subtitles = [
        {
            'start_time': 0.0,
            'end_time': 3.0,
            'eng': 'Hello, world!',
            'english': 'Hello, world!',
            'kor': '안녕하세요!',
            'korean': '안녕하세요!'
        },
        {
            'start_time': 3.5,
            'end_time': 6.0,
            'eng': 'This is a test.',
            'english': 'This is a test.',
            'kor': '이것은 테스트입니다.',
            'korean': '이것은 테스트입니다.'
        }
    ]
    
    # 일반 버전 테스트
    output_path_normal = "test_normal.ass"
    generator.generate_ass(test_subtitles, output_path_normal, is_shorts=False)
    
    # 쇼츠 버전 테스트
    output_path_shorts = "test_shorts.ass"
    generator.generate_ass(test_subtitles, output_path_shorts, is_shorts=True)
    
    # 생성된 파일 내용 확인
    print("\n1. Normal ASS file (일반 버전):")
    print("-" * 60)
    with open(output_path_normal, 'r', encoding='utf-8') as f:
        content = f.read()
        # 스타일 부분만 출력
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '[V4+ Styles]' in line:
                for j in range(i, min(i + 10, len(lines))):
                    print(lines[j])
                break
    
    print("\n2. Shorts ASS file (쇼츠 버전):")
    print("-" * 60)
    with open(output_path_shorts, 'r', encoding='utf-8') as f:
        content = f.read()
        # 스타일 부분만 출력
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '[V4+ Styles]' in line:
                for j in range(i, min(i + 10, len(lines))):
                    print(lines[j])
                break
    
    # 파일 삭제
    os.remove(output_path_normal)
    os.remove(output_path_shorts)

def test_extract_route():
    """extract.py의 create_multi_subtitle_file 테스트"""
    print("\n" + "=" * 60)
    print("Testing create_multi_subtitle_file from extract.py")
    print("=" * 60)
    
    # 테스트 자막 데이터
    test_subtitles = [
        SubtitleInfo(start=0.0, end=3.0, eng="Hello, world!", kor="안녕하세요!"),
        SubtitleInfo(start=3.5, end=6.0, eng="This is a test.", kor="이것은 테스트입니다.")
    ]
    
    # 일반 버전 테스트
    output_path_normal = Path("test_extract_normal.ass")
    create_multi_subtitle_file(output_path_normal, test_subtitles, 0.0, is_shorts=False)
    
    # 쇼츠 버전 테스트
    output_path_shorts = Path("test_extract_shorts.ass")
    create_multi_subtitle_file(output_path_shorts, test_subtitles, 0.0, is_shorts=True)
    
    # 생성된 파일 내용 확인
    print("\n3. Extract Normal ASS file (일반 버전):")
    print("-" * 60)
    with open(output_path_normal, 'r', encoding='utf-8') as f:
        content = f.read()
        # 스타일 부분만 출력
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '[V4+ Styles]' in line:
                for j in range(i, min(i + 10, len(lines))):
                    print(lines[j])
                break
    
    print("\n4. Extract Shorts ASS file (쇼츠 버전):")
    print("-" * 60)
    with open(output_path_shorts, 'r', encoding='utf-8') as f:
        content = f.read()
        # 스타일 부분만 출력
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '[V4+ Styles]' in line:
                for j in range(i, min(i + 10, len(lines))):
                    print(lines[j])
                break
    
    # 파일 삭제
    os.remove(output_path_normal)
    os.remove(output_path_shorts)

if __name__ == "__main__":
    print("🔍 Testing ASS Generation with styles.py settings\n")
    
    # 직접 ASSGenerator 테스트
    test_ass_generator()
    
    # extract.py 경유 테스트
    test_extract_route()
    
    print("\n✅ Test completed!")