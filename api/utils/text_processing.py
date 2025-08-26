"""
Text Processing Utilities
"""
import re
from typing import List


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