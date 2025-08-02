#!/usr/bin/env python3
"""
Test blank+Korean subtitle generation
블랭크+한글 자막 생성 테스트
"""

from subtitle_generator import SubtitleGenerator
import tempfile

def test_blank_korean():
    """Test blank subtitle with Korean"""
    generator = SubtitleGenerator()
    
    # Test data
    subtitle_data = {
        'start_time': 0,
        'end_time': 5.0,
        'eng': 'I love learning new languages',
        'english': 'I love learning new languages',
        'kor': '나는 새로운 언어를 배우는 것을 좋아해요',
        'korean': '나는 새로운 언어를 배우는 것을 좋아해요',
        'note': '언어 학습',
        'keywords': ['love', 'learning', 'languages'],
        'text_eng_blank': 'I ____ ________ new _________'
    }
    
    # Test 1: Blank only (no Korean)
    print("\n=== Test 1: Blank only (no Korean) ===")
    temp_file1 = tempfile.NamedTemporaryFile(suffix='_blank_only.ass', delete=False)
    temp_file1.close()
    
    result = generator.generate_blank_subtitle(subtitle_data, temp_file1.name, with_korean=False)
    print(f"Result: {result}")
    
    with open(temp_file1.name, 'r', encoding='utf-8') as f:
        content = f.read()
        print("File content:")
        print(content[-500:])  # Last 500 chars to see the dialogue line
    
    # Test 2: Blank with Korean
    print("\n=== Test 2: Blank with Korean ===")
    temp_file2 = tempfile.NamedTemporaryFile(suffix='_blank_korean.ass', delete=False)
    temp_file2.close()
    
    result = generator.generate_blank_subtitle(subtitle_data, temp_file2.name, with_korean=True)
    print(f"Result: {result}")
    
    with open(temp_file2.name, 'r', encoding='utf-8') as f:
        content = f.read()
        print("File content:")
        print(content[-500:])  # Last 500 chars to see the dialogue line
    
    print(f"\nGenerated files:")
    print(f"  - {temp_file1.name}")
    print(f"  - {temp_file2.name}")

if __name__ == "__main__":
    test_blank_korean()