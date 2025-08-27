"""
Text Processing Utilities
"""
import re
from typing import List
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from styles import get_ass_styles_section


def generate_blank_text(text: str, keywords: List[str]) -> str:
    """키워드를 블랭크 처리 (띄어쓰기 유지)"""
    if not keywords:
        return text
    
    blank_text = text
    for keyword in keywords:
        # 대소문자 구분 없이 찾되, 원본의 대소문자는 유지
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        # 띄어쓰기는 그대로 유지하면서 문자만 _ 로 대체
        def replace_with_blanks(match):
            matched_text = match.group()
            # 각 문자를 확인하여 공백은 유지, 문자는 _로 대체
            return ''.join('_' if char != ' ' else ' ' for char in matched_text)
        
        blank_text = pattern.sub(replace_with_blanks, blank_text)
    
    return blank_text


def create_multi_subtitle_file(output_path: Path, subtitles: List[dict], start_offset: float = 0, is_shorts: bool = False):
    """여러 자막을 타이밍에 맞춰 ASS 파일로 생성 - ASSGenerator 사용
    
    Args:
        output_path: ASS 파일 출력 경로
        subtitles: 자막 리스트 [{"start": float, "end": float, "eng": str, "kor": str}]
        start_offset: 시작 시간 오프셋 (초)
        is_shorts: 쇼츠용 여부 (기본값 False)
    """
    # Import here to avoid circular import
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from ass_generator import ASSGenerator
    
    # ASSGenerator 사용
    generator = ASSGenerator()
    
    # 자막 데이터 변환
    subtitle_data = []
    for sub in subtitles:
        sub_dict = {
            'start_time': max(0, sub['start'] - start_offset),
            'end_time': max(0.1, sub['end'] - start_offset)
        }
        if sub.get('eng'):
            sub_dict['eng'] = sub['eng']
            sub_dict['english'] = sub['eng']  # ASSGenerator 호환성
        if sub.get('kor'):
            sub_dict['kor'] = sub['kor']
            sub_dict['korean'] = sub['kor']  # ASSGenerator 호환성
        subtitle_data.append(sub_dict)
    
    # ASS 파일 생성 (is_shorts 매개변수 전달)
    generator.generate_ass(subtitle_data, str(output_path), is_shorts=is_shorts)
    
    return str(output_path)