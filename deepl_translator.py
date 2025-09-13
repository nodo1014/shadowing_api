"""
DeepL Translation Module
자막의 text_en 필드가 없을 때 DeepL로 번역하는 모듈
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DeepLTranslator:
    """DeepL API를 사용한 번역 클래스"""
    
    def __init__(self, api_key: str = None):
        """
        DeepL 번역기 초기화
        
        Args:
            api_key: DeepL API 키. 없으면 환경변수에서 가져옴
        """
        self.api_key = api_key or os.getenv('DEEPL_API_KEY')
        if not self.api_key:
            logger.warning("DeepL API key not found. Translation will be skipped.")
            self.enabled = False
        else:
            self.enabled = True
        
        # DeepL API 엔드포인트
        # Free API: https://api-free.deepl.com/v2/translate
        # Pro API: https://api.deepl.com/v2/translate
        if self.enabled:
            if self.api_key.endswith(":fx"):  # Free API key format
                self.api_url = "https://api-free.deepl.com/v2/translate"
            else:
                self.api_url = "https://api.deepl.com/v2/translate"
    
    def translate_text(self, text: str, source_lang: str = "KO", target_lang: str = "EN") -> Optional[str]:
        """
        텍스트를 번역합니다.
        
        Args:
            text: 번역할 텍스트
            source_lang: 소스 언어 코드 (기본: KO)
            target_lang: 타겟 언어 코드 (기본: EN)
            
        Returns:
            번역된 텍스트 또는 None (실패시)
        """
        if not self.enabled:
            return None
            
        try:
            headers = {
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "text": text,
                "source_lang": source_lang,
                "target_lang": target_lang
            }
            
            response = requests.post(self.api_url, headers=headers, data=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("translations"):
                return result["translations"][0]["text"]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepL translation error: {e}")
            return None
    
    def translate_batch(self, texts: List[str], source_lang: str = "KO", target_lang: str = "EN") -> List[Optional[str]]:
        """
        여러 텍스트를 한번에 번역합니다.
        
        Args:
            texts: 번역할 텍스트 리스트
            source_lang: 소스 언어 코드
            target_lang: 타겟 언어 코드
            
        Returns:
            번역된 텍스트 리스트 (실패한 항목은 None)
        """
        if not self.enabled:
            return [None] * len(texts)
            
        try:
            headers = {
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # DeepL은 여러 텍스트를 한번에 보낼 수 있음
            data = {
                "source_lang": source_lang,
                "target_lang": target_lang
            }
            
            # 여러 텍스트를 text[] 파라미터로 전송
            data_list = []
            for text in texts:
                data_list.append(("text", text))
            
            response = requests.post(self.api_url, headers=headers, data=data_list + list(data.items()))
            response.raise_for_status()
            
            result = response.json()
            translations = result.get("translations", [])
            
            # 결과를 순서대로 매핑
            translated_texts = []
            for i in range(len(texts)):
                if i < len(translations):
                    translated_texts.append(translations[i]["text"])
                else:
                    translated_texts.append(None)
            
            return translated_texts
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepL batch translation error: {e}")
            return [None] * len(texts)


class SubtitleTranslator:
    """자막 파일 번역 클래스"""
    
    def __init__(self, translator: DeepLTranslator = None):
        """
        자막 번역기 초기화
        
        Args:
            translator: DeepL 번역기 인스턴스. 없으면 새로 생성
        """
        self.translator = translator or DeepLTranslator()
    
    def load_and_translate_subtitles(self, subtitle_file: str) -> List[Dict]:
        """
        자막 파일을 로드하고 text_en이 없으면 번역합니다.
        
        Args:
            subtitle_file: 자막 파일 경로 (.json)
            
        Returns:
            번역된 자막 데이터 리스트
        """
        subtitle_path = Path(subtitle_file)
        
        if not subtitle_path.exists():
            logger.error(f"Subtitle file not found: {subtitle_file}")
            return []
        
        try:
            # JSON 파일 로드
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitles = json.load(f)
            
            # 리스트가 아니면 리스트로 변환
            if isinstance(subtitles, dict):
                subtitles = [subtitles]
            
            # 번역이 필요한 항목 찾기
            items_to_translate = []
            indices_to_translate = []
            
            for i, subtitle in enumerate(subtitles):
                # text_en 또는 text_eng가 없거나 비어있는 경우
                if not subtitle.get('text_en') and not subtitle.get('text_eng'):
                    # text_kor이 있는 경우에만 번역
                    if subtitle.get('text_kor'):
                        items_to_translate.append(subtitle['text_kor'])
                        indices_to_translate.append(i)
            
            # 번역이 필요한 항목이 있으면 번역
            if items_to_translate:
                logger.info(f"Translating {len(items_to_translate)} subtitles...")
                translated_texts = self.translator.translate_batch(items_to_translate)
                
                # 번역 결과 적용
                for idx, translated_text in zip(indices_to_translate, translated_texts):
                    if translated_text:
                        subtitles[idx]['text_en'] = translated_text
                        # text_eng 필드도 동시에 업데이트 (호환성)
                        subtitles[idx]['text_eng'] = translated_text
                        logger.debug(f"Translated: '{subtitles[idx]['text_kor']}' -> '{translated_text}'")
                
                # 번역된 내용을 파일에 저장
                with open(subtitle_path, 'w', encoding='utf-8') as f:
                    json.dump(subtitles, f, ensure_ascii=False, indent=2)
                logger.info(f"Updated subtitle file with translations: {subtitle_file}")
            
            return subtitles
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse subtitle file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing subtitle file: {e}")
            return []
    
    def ensure_translation(self, subtitle_data: Dict) -> Dict:
        """
        단일 자막 항목의 번역을 보장합니다.
        
        Args:
            subtitle_data: 자막 데이터 딕셔너리
            
        Returns:
            번역이 완료된 자막 데이터
        """
        # text_en 또는 text_eng가 없고 text_kor이 있는 경우
        if not subtitle_data.get('text_en') and not subtitle_data.get('text_eng') and subtitle_data.get('text_kor'):
            translated_text = self.translator.translate_text(subtitle_data['text_kor'])
            if translated_text:
                subtitle_data['text_en'] = translated_text
                subtitle_data['text_eng'] = translated_text
                logger.debug(f"Translated: '{subtitle_data['text_kor']}' -> '{translated_text}'")
        
        return subtitle_data


# 편의 함수
def load_subtitles_with_translation(subtitle_file: str) -> List[Dict]:
    """
    자막 파일을 로드하고 필요시 번역합니다.
    
    Args:
        subtitle_file: 자막 파일 경로
        
    Returns:
        번역된 자막 리스트
    """
    translator = SubtitleTranslator()
    return translator.load_and_translate_subtitles(subtitle_file)


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)
    
    # 환경변수에서 API 키를 가져와 테스트
    try:
        translator = DeepLTranslator()
        
        # 단일 번역 테스트
        korean_text = "안녕하세요"
        english_text = translator.translate_text(korean_text)
        print(f"단일 번역: {korean_text} -> {english_text}")
        
        # 배치 번역 테스트
        korean_texts = ["안녕하세요", "감사합니다", "좋은 하루 되세요"]
        english_texts = translator.translate_batch(korean_texts)
        print("배치 번역:")
        for k, e in zip(korean_texts, english_texts):
            print(f"  {k} -> {e}")
            
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set DEEPL_API_KEY environment variable")