"""
Subtitle generation components
자막 생성을 위한 독립적인 컴포넌트들
"""
import logging
from typing import Dict, List, Optional
import re
from ass_generator import ASSGenerator

# Configure logging
logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """자막 생성을 위한 통합 클래스"""
    
    def __init__(self):
        self.ass_generator = ASSGenerator()
    
    def generate_full_subtitle(self, subtitle_data: Dict, output_path: str, 
                             with_keywords: bool = False, clip_duration: float = None,
                             gap_duration: float = 0.0) -> bool:
        """완전한 영한 자막 생성"""
        try:
            subtitle = subtitle_data.copy()
            
            # Type 2의 경우 keywords 필드 추가
            if with_keywords and 'keywords' in subtitle_data:
                subtitle['keywords'] = subtitle_data['keywords']
            
            # Pass total duration including gap for last subtitle extension
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass([subtitle], output_path, clip_duration=total_duration)
            return True
        except Exception as e:
            logger.error(f"Error generating full subtitle: {e}", exc_info=True)
            return False
    
    def generate_blank_subtitle(self, subtitle_data: Dict, output_path: str,
                              with_korean: bool = False, clip_duration: float = None,
                              gap_duration: float = 0.0) -> bool:
        """블랭크 자막 생성 (영어만 블랭크 또는 블랭크+한글)"""
        try:
            logger.debug(f"[BLANK DEBUG] with_korean={with_korean}, subtitle_data keys: {subtitle_data.keys()}")
            subtitle = subtitle_data.copy()
            
            # 영어 텍스트 블랭크 처리
            if 'text_eng_blank' in subtitle_data and subtitle_data['text_eng_blank'] is not None:
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
                korean_text = None
                if 'korean' in subtitle_data:
                    korean_text = subtitle_data['korean']
                elif 'kor' in subtitle_data:
                    korean_text = subtitle_data['kor']
                
                logger.debug(f"[BLANK DEBUG] Korean text found: {korean_text}")
                if korean_text:
                    subtitle['kor'] = korean_text
                    subtitle['korean'] = korean_text
                else:
                    logger.warning("[BLANK DEBUG] No Korean text found in subtitle_data!")
            
            # 노트는 유지 (학습에 도움)
            
            logger.debug(f"[BLANK DEBUG] Final subtitle: eng='{subtitle.get('eng', '')}', kor='{subtitle.get('kor', '')}'")
            
            # Pass total duration including gap for last subtitle extension
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass([subtitle], output_path, clip_duration=total_duration)
            return True
        except Exception as e:
            logger.error(f"Error generating blank subtitle: {e}", exc_info=True)
            return False
    
    def generate_korean_only_subtitle(self, subtitle_data: Dict, output_path: str,
                                    with_note: bool = True, clip_duration: float = None,
                                    gap_duration: float = 0.0) -> bool:
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
            
            # Pass total duration including gap for last subtitle extension
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass([subtitle], output_path, clip_duration=total_duration)
            return True
        except Exception as e:
            logger.error(f"Error generating Korean-only subtitle: {e}", exc_info=True)
            return False
    
    def _create_blanks(self, text: str, keywords: List[str]) -> str:
        """키워드를 블랭크 처리"""
        if not keywords:
            # keywords가 없으면 전체 텍스트를 블랭크 처리
            return ''.join('_' if char != ' ' else ' ' for char in text)
        
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