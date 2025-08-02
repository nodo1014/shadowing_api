"""
Subtitle generation components
자막 생성을 위한 독립적인 컴포넌트들
"""
from typing import Dict, List, Optional
import re
from ass_generator import ASSGenerator


class SubtitleGenerator:
    """자막 생성을 위한 통합 클래스"""
    
    def __init__(self):
        self.ass_generator = ASSGenerator()
    
    def generate_full_subtitle(self, subtitle_data: Dict, output_path: str, 
                             with_keywords: bool = False) -> bool:
        """완전한 영한 자막 생성"""
        try:
            subtitle = subtitle_data.copy()
            
            # Type 2의 경우 keywords 필드 추가
            if with_keywords and 'keywords' in subtitle_data:
                subtitle['keywords'] = subtitle_data['keywords']
            
            self.ass_generator.generate_ass([subtitle], output_path)
            return True
        except Exception as e:
            print(f"Error generating full subtitle: {e}")
            return False
    
    def generate_blank_subtitle(self, subtitle_data: Dict, output_path: str,
                              with_korean: bool = False) -> bool:
        """블랭크 자막 생성 (영어만 블랭크 또는 블랭크+한글)"""
        try:
            subtitle = subtitle_data.copy()
            
            # 영어 텍스트 블랭크 처리
            if 'text_eng_blank' in subtitle_data:
                subtitle['eng'] = subtitle_data['text_eng_blank']
                subtitle['english'] = subtitle_data['text_eng_blank']
            else:
                # 블랭크 생성
                blank_text = self._create_blanks(
                    subtitle_data.get('text_eng', subtitle_data.get('eng', '')),
                    subtitle_data.get('keywords', [])
                )
                subtitle['eng'] = blank_text
                subtitle['english'] = blank_text
            
            # 한글 처리
            if not with_korean:
                subtitle['kor'] = ''
                subtitle['korean'] = ''
            else:
                # 한글은 유지
                if 'korean' in subtitle_data:
                    subtitle['kor'] = subtitle_data['korean']
                    subtitle['korean'] = subtitle_data['korean']
                elif 'kor' in subtitle_data:
                    subtitle['kor'] = subtitle_data['kor']
                    subtitle['korean'] = subtitle_data['kor']
            
            # 노트는 제거
            subtitle['note'] = ''
            
            self.ass_generator.generate_ass([subtitle], output_path)
            return True
        except Exception as e:
            print(f"Error generating blank subtitle: {e}")
            return False
    
    def generate_korean_only_subtitle(self, subtitle_data: Dict, output_path: str,
                                    with_note: bool = True) -> bool:
        """한글만 있는 자막 생성"""
        try:
            subtitle = subtitle_data.copy()
            
            # 영어 제거
            subtitle['eng'] = ''
            subtitle['english'] = ''
            
            # 한글 유지
            if 'korean' in subtitle_data:
                subtitle['kor'] = subtitle_data['korean']
                subtitle['korean'] = subtitle_data['korean']
            elif 'kor' in subtitle_data:
                subtitle['kor'] = subtitle_data['kor']
                subtitle['korean'] = subtitle_data['kor']
            
            # 노트 처리
            if not with_note:
                subtitle['note'] = ''
            
            self.ass_generator.generate_ass([subtitle], output_path)
            return True
        except Exception as e:
            print(f"Error generating Korean-only subtitle: {e}")
            return False
    
    def _create_blanks(self, text: str, keywords: List[str]) -> str:
        """키워드를 블랭크 처리"""
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