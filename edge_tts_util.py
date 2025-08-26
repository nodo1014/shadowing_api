"""
Edge TTS utility for text-to-speech generation
Microsoft Edge TTS를 활용한 음성 합성 유틸리티
"""
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional
import edge_tts

logger = logging.getLogger(__name__)


class EdgeTTSGenerator:
    """Edge TTS 생성기"""
    
    # 지원 음성 목록
    VOICES = {
        'ko-KR-SunHiNeural': 'ko-KR',  # 한국어 여성 (선희)
        'ko-KR-InJoonNeural': 'ko-KR',  # 한국어 남성 (인준)
        'en-US-AriaNeural': 'en-US',    # 영어 여성
        'en-US-GuyNeural': 'en-US',     # 영어 남성
    }
    
    def __init__(self, voice: str = 'ko-KR-SunHiNeural', rate: str = '+0%', pitch: str = '+0Hz'):
        """
        Args:
            voice: 음성 종류 (기본: 한국어 선희)
            rate: 속도 조절 (-50% ~ +50%)
            pitch: 피치 조절 (-50Hz ~ +50Hz)
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        
    async def generate_tts_async(self, text: str, output_path: str) -> bool:
        """비동기 TTS 생성"""
        try:
            # Edge TTS 통신 객체 생성
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch
            )
            
            # 오디오 파일 저장
            await communicate.save(output_path)
            
            logger.info(f"TTS generated: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return False
    
    def generate_tts(self, text: str, output_path: str) -> bool:
        """동기 TTS 생성"""
        try:
            # 비동기 함수를 동기적으로 실행
            asyncio.run(self.generate_tts_async(text, output_path))
            return True
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return False
    
    async def generate_tts_for_clips(self, clips: list, voice_map: dict = None) -> dict:
        """여러 클립에 대한 TTS 생성
        
        Args:
            clips: 클립 정보 리스트 [{text_eng, text_kor}, ...]
            voice_map: 언어별 음성 매핑 {'ko': 'ko-KR-SunHiNeural', 'en': 'en-US-AriaNeural'}
            
        Returns:
            클립별 TTS 파일 경로 딕셔너리
        """
        if voice_map is None:
            voice_map = {
                'ko': 'ko-KR-SunHiNeural',
                'en': 'en-US-AriaNeural'
            }
        
        tts_files = {}
        
        for idx, clip in enumerate(clips):
            clip_tts = {}
            
            # 한국어 TTS
            if clip.get('text_kor'):
                kor_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                kor_file.close()
                
                self.voice = voice_map.get('ko', 'ko-KR-SunHiNeural')
                if await self.generate_tts_async(clip['text_kor'], kor_file.name):
                    clip_tts['kor'] = kor_file.name
            
            # 영어 TTS
            if clip.get('text_eng'):
                eng_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                eng_file.close()
                
                self.voice = voice_map.get('en', 'en-US-AriaNeural')
                if await self.generate_tts_async(clip['text_eng'], eng_file.name):
                    clip_tts['eng'] = eng_file.name
            
            tts_files[idx] = clip_tts
        
        return tts_files


# 사용 예시
async def test_tts():
    """TTS 테스트"""
    generator = EdgeTTSGenerator()
    
    # 단일 TTS 생성
    await generator.generate_tts_async("안녕하세요, 반갑습니다.", "test_ko.mp3")
    
    # 여러 클립 TTS 생성
    clips = [
        {'text_eng': 'Hello, how are you?', 'text_kor': '안녕하세요, 어떻게 지내세요?'},
        {'text_eng': 'Nice to meet you.', 'text_kor': '만나서 반갑습니다.'}
    ]
    
    tts_files = await generator.generate_tts_for_clips(clips)
    print(f"Generated TTS files: {tts_files}")


if __name__ == "__main__":
    asyncio.run(test_tts())