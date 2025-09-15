"""
Efficient subtitle pipeline for video clipping
효율적인 자막 파이프라인
"""
from typing import Dict, List, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum
import tempfile
import os
from ass_generator import ASSGenerator


class SubtitleType(Enum):
    """자막 타입 정의"""
    FULL = "full"  # 영어 + 한국어
    BLANK = "blank"  # 키워드 블랭크 처리된 영어
    BLANK_KOREAN = "blank_korean"  # 블랭크 영어 + 한국어
    KOREAN_ONLY = "korean_only"  # 한국어만
    ENGLISH_ONLY = "english_only"  # 영어만
    KOREAN_WITH_NOTE = "korean_with_note"  # 한국어 + 노트


@dataclass
class SubtitleVariant:
    """자막 변형 데이터"""
    english: str
    korean: str
    note: Optional[str] = None
    keywords: Optional[List[str]] = None
    variant_type: SubtitleType = SubtitleType.FULL
    
    def to_subtitle_data(self, start_time: float, end_time: float) -> Dict:
        """ASS 생성을 위한 자막 데이터로 변환"""
        data = {
            'start_time': start_time,
            'end_time': end_time,
            'eng': self.english,
            'kor': self.korean,
            'english': self.english,  # 호환성
            'korean': self.korean,    # 호환성
        }
        
        if self.note:
            data['note'] = self.note
        if self.keywords:
            data['keywords'] = self.keywords
            
        return data


class SubtitlePipeline:
    """효율적인 자막 처리 파이프라인"""
    
    def __init__(self, base_subtitle_data: Dict):
        """
        Args:
            base_subtitle_data: 기본 자막 데이터
                - english: 영어 텍스트
                - korean: 한국어 텍스트
                - note: 노트 (선택)
                - keywords: 키워드 리스트 (선택)
                - start_time: 시작 시간
                - end_time: 종료 시간
        """
        self.base_data = base_subtitle_data
        self._variants = {}
        self._ass_generator = ASSGenerator()
        self._blank_text_cache = {}
        
        # 기본 데이터 검증
        # 쇼츠 여부 확인하고 적절한 텍스트 선택
        is_shorts = base_subtitle_data.get('is_shorts', False)
        if is_shorts:
            # 쇼츠용 짧은 버전 우선 사용
            self.english = base_subtitle_data.get('text_eng') or \
                         base_subtitle_data.get('eng_text_s') or \
                         base_subtitle_data.get('english', '')
            self.korean = base_subtitle_data.get('text_kor') or \
                        base_subtitle_data.get('kor_text_s') or \
                        base_subtitle_data.get('korean', '')
        else:
            # 일반용 긴 버전 사용
            self.english = base_subtitle_data.get('text_eng') or \
                         base_subtitle_data.get('eng_text_l') or \
                         base_subtitle_data.get('english', '')
            self.korean = base_subtitle_data.get('text_kor') or \
                        base_subtitle_data.get('kor_text_l') or \
                        base_subtitle_data.get('korean', '')
        
        self.note = base_subtitle_data.get('note', '')
        self.keywords = base_subtitle_data.get('keywords') or []
        self.start_time = base_subtitle_data.get('start_time', 0)
        self.end_time = base_subtitle_data.get('end_time', 0)
        self.is_shorts = is_shorts  # 쇼츠 여부 저장
        
    def get_variant(self, variant_type: SubtitleType) -> SubtitleVariant:
        """자막 변형 가져오기 (캐싱 적용)"""
        if variant_type not in self._variants:
            self._variants[variant_type] = self._generate_variant(variant_type)
        return self._variants[variant_type]
    
    def _generate_variant(self, variant_type: SubtitleType) -> SubtitleVariant:
        """자막 변형 생성"""
        if variant_type == SubtitleType.FULL:
            return SubtitleVariant(
                english=self.english,
                korean=self.korean,
                note=self.note,
                keywords=self.keywords,
                variant_type=variant_type
            )
            
        elif variant_type == SubtitleType.BLANK:
            blank_text = self._get_blank_text(self.english)
            return SubtitleVariant(
                english=blank_text,
                korean='',  # 블랭크만
                note=self.note,
                variant_type=variant_type
            )
            
        elif variant_type == SubtitleType.BLANK_KOREAN:
            blank_text = self._get_blank_text(self.english)
            return SubtitleVariant(
                english=blank_text,
                korean=self.korean,
                note=self.note,
                variant_type=variant_type
            )
            
        elif variant_type == SubtitleType.KOREAN_ONLY:
            return SubtitleVariant(
                english='',
                korean=self.korean,
                note=self.note,
                variant_type=variant_type
            )
            
        elif variant_type == SubtitleType.ENGLISH_ONLY:
            return SubtitleVariant(
                english=self.english,
                korean='',
                note=self.note,
                keywords=self.keywords,
                variant_type=variant_type
            )
            
        elif variant_type == SubtitleType.KOREAN_WITH_NOTE:
            return SubtitleVariant(
                english='',
                korean=self.korean,
                note=self.note,
                variant_type=variant_type
            )
            
        else:
            raise ValueError(f"Unknown variant type: {variant_type}")
    
    def _get_blank_text(self, text: str) -> str:
        """블랭크 텍스트 생성 (캐싱 적용)"""
        # 캐시 키 생성
        cache_key = f"{text}:{','.join(self.keywords or [])}"
        
        if cache_key in self._blank_text_cache:
            return self._blank_text_cache[cache_key]
        
        # 블랭크 텍스트 생성
        blank_text = self._generate_blank_text(text, self.keywords)
        self._blank_text_cache[cache_key] = blank_text
        
        return blank_text
    
    def _generate_blank_text(self, text: str, keywords: List[str]) -> str:
        """키워드를 블랭크 처리"""
        if not keywords:
            return text
        
        blank_text = text
        # 키워드를 길이 순으로 정렬 (긴 것부터)
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        
        for keyword in sorted_keywords:
            # 대소문자 구분 없이 찾되, 원본의 대소문자는 유지
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            # 띄어쓰기는 그대로 유지하면서 문자만 _ 로 대체
            def replace_with_blanks(match):
                matched_text = match.group()
                return ''.join('_' if char != ' ' else ' ' for char in matched_text)
            
            blank_text = pattern.sub(replace_with_blanks, blank_text)
        
        return blank_text
    
    def generate_ass_content(self, variant_type: SubtitleType, clip_duration: float = None) -> str:
        """ASS 콘텐츠를 메모리에서 생성"""
        variant = self.get_variant(variant_type)
        subtitle_data = variant.to_subtitle_data(self.start_time, self.end_time)
        
        # 임시로 메모리에서 ASS 생성
        ass_content = self._generate_ass_in_memory([subtitle_data], clip_duration)
        return ass_content
    
    def _generate_ass_in_memory(self, subtitles: List[Dict], clip_duration: float = None) -> str:
        """메모리에서 ASS 콘텐츠 생성"""
        # ASS 헤더
        content = self._ass_generator._generate_header()
        # ASS 스타일 (쇼츠 여부 전달)
        content += self._ass_generator._generate_styles(self.is_shorts)
        # ASS 이벤트
        
        # 타이밍 조정
        adjusted_subtitles = []
        for sub in subtitles:
            adjusted_sub = sub.copy()
            if clip_duration is not None:
                # 마지막 자막은 클립 전체 길이로 확장
                if sub == subtitles[-1] or len(subtitles) == 1:
                    adjusted_sub['start_time'] = 0
                    adjusted_sub['end_time'] = clip_duration
                else:
                    adjusted_sub['start_time'] = sub['start_time']
                    adjusted_sub['end_time'] = sub['end_time']
            adjusted_subtitles.append(adjusted_sub)
        
        content += self._ass_generator._generate_events(adjusted_subtitles)
        return content
    
    def save_variant_to_file(self, variant_type: SubtitleType, output_path: str, clip_duration: float = None):
        """필요한 경우에만 파일로 저장"""
        content = self.generate_ass_content(variant_type, clip_duration)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def get_all_variants(self) -> Dict[SubtitleType, SubtitleVariant]:
        """모든 변형 한 번에 생성 (배치 처리용)"""
        for variant_type in SubtitleType:
            self.get_variant(variant_type)
        return self._variants.copy()
    
    def create_template_subtitles(self, template_number: int, clip_duration: float = None) -> Dict[str, str]:
        """템플릿별 필요한 자막 파일 생성"""
        subtitle_files = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            if template_number == 1:
                # Type 1: 무자막, 영한자막
                if self.english or self.korean:
                    full_path = os.path.join(temp_dir, "full.ass")
                    self.save_variant_to_file(SubtitleType.FULL, full_path, clip_duration)
                    subtitle_files['full'] = full_path
                    
            elif template_number == 2:
                # Type 2: 무자막, 블랭크+한국어, 영한자막
                if self.keywords and self.english:
                    blank_korean_path = os.path.join(temp_dir, "blank_korean.ass")
                    self.save_variant_to_file(SubtitleType.BLANK_KOREAN, blank_korean_path, clip_duration)
                    subtitle_files['blank_korean'] = blank_korean_path
                
                if self.english or self.korean:
                    full_path = os.path.join(temp_dir, "full.ass")
                    self.save_variant_to_file(SubtitleType.FULL, full_path, clip_duration)
                    subtitle_files['full'] = full_path
                    
            elif template_number == 3:
                # Type 3: Progressive learning
                if self.english:
                    english_path = os.path.join(temp_dir, "english.ass")
                    self.save_variant_to_file(SubtitleType.ENGLISH_ONLY, english_path, clip_duration)
                    subtitle_files['english'] = english_path
                
                if self.korean:
                    korean_path = os.path.join(temp_dir, "korean.ass")
                    self.save_variant_to_file(SubtitleType.KOREAN_ONLY, korean_path, clip_duration)
                    subtitle_files['korean'] = korean_path
                
                if self.english or self.korean:
                    full_path = os.path.join(temp_dir, "full.ass")
                    self.save_variant_to_file(SubtitleType.FULL, full_path, clip_duration)
                    subtitle_files['full'] = full_path
        
        return subtitle_files


# 사용 예시
if __name__ == "__main__":
    # 테스트 자막 데이터
    subtitle_data = {
        'english': 'Hello, how are you today?',
        'korean': '안녕하세요, 오늘 어떻게 지내세요?',
        'note': '인사 표현',
        'keywords': ['Hello', 'how'],
        'start_time': 0,
        'end_time': 5
    }
    
    # 파이프라인 생성
    pipeline = SubtitlePipeline(subtitle_data)
    
    # 다양한 변형 가져오기
    full_variant = pipeline.get_variant(SubtitleType.FULL)
    blank_variant = pipeline.get_variant(SubtitleType.BLANK)
    blank_korean_variant = pipeline.get_variant(SubtitleType.BLANK_KOREAN)
    
    print(f"Full: {full_variant.english} / {full_variant.korean}")
    print(f"Blank: {blank_variant.english}")
    print(f"Blank+Korean: {blank_korean_variant.english} / {blank_korean_variant.korean}")
    
    # 템플릿 2용 자막 생성
    subtitle_files = pipeline.create_template_subtitles(template_number=2, clip_duration=10.0)
    print(f"Generated files: {subtitle_files}")