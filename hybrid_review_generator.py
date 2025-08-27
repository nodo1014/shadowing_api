"""
Hybrid Review Clip Generator
하이브리드 방식 리뷰 클립 생성기 (ASS + FFmpeg 효과)
"""
import os
import tempfile
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from edge_tts_util import EdgeTTSGenerator
from ass_generator import ASSGenerator

logger = logging.getLogger(__name__)


class HybridReviewGenerator:
    """하이브리드 리뷰 생성기"""
    
    def __init__(self):
        self.tts_generator = EdgeTTSGenerator()
        self.ass_generator = ASSGenerator()
        
    async def create_review_clip(self, clips_data: List[Dict], 
                                media_path: str,
                                output_path: str,
                                title: str = "Speed Review", 
                                template_number: int = 11,
                                clip_timestamps: List[Tuple[float, float]] = None) -> bool:
        """하이브리드 방식으로 리뷰 클립 생성
        
        Args:
            clips_data: 클립 데이터 리스트
            media_path: 원본 미디어 경로 (배경용)
            output_path: 출력 파일 경로
            title: 리뷰 제목
            template_number: 템플릿 번호
        """
        try:
            # 쇼츠 여부 확인
            is_shorts = template_number in [11, 12, 13]
            width = 1080 if is_shorts else 1920
            height = 1920 if is_shorts else 1080
            
            # 1. ASS 자막 생성 (애니메이션 텍스트)
            ass_file = await self._create_animated_ass(clips_data, title, is_shorts)
            
            # 2. TTS 오디오 생성 및 병합
            audio_file = await self._create_merged_tts(clips_data)
            
            # 3. 배경 비디오 준비 (원본을 흐리게)
            background = await self._prepare_background(media_path, width, height, audio_file)
            
            # 4. 최종 합성
            success = await self._compose_final_video(
                background, ass_file, audio_file, output_path, width, height
            )
            
            # 임시 파일 정리
            for temp_file in [ass_file, audio_file, background]:
                if temp_file and os.path.exists(temp_file):
                    os.unlink(temp_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating hybrid review clip: {e}", exc_info=True)
            return False
    
    async def _create_animated_ass(self, clips_data: List[Dict], 
                                  title: str, is_shorts: bool) -> str:
        """애니메이션 ASS 자막 생성"""
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.ass', delete=False)
        temp_file.close()
        
        # ASS 헤더 (고급 스타일)
        styles = self._create_review_styles(is_shorts)
        
        # 이벤트 생성 (애니메이션 효과 포함)
        events = []
        current_time = 0.0
        
        # 타이틀 애니메이션 (2초)
        events.append(self._create_title_event(title, 0, 2))
        current_time = 2.5
        
        # 각 클립 텍스트 애니메이션
        for idx, clip in enumerate(clips_data):
            # 한국어 (위)
            events.append(self._create_text_event(
                clip['text_kor'], 
                current_time, 
                current_time + 3,
                'ReviewKor',
                fade_in=True
            ))
            
            # 영어 (아래) - 0.3초 딜레이
            events.append(self._create_text_event(
                clip['text_eng'],
                current_time + 0.3,
                current_time + 3,
                'ReviewEng',
                fade_in=True,
                slide=True
            ))
            
            current_time += 3.5  # 다음 클립으로
        
        # ASS 파일 작성
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(self._generate_ass_header(is_shorts))
            f.write(styles)
            f.write("\n[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for event in events:
                f.write(event + "\n")
        
        return temp_file.name
    
    def _create_review_styles(self, is_shorts: bool) -> str:
        """리뷰용 ASS 스타일 정의"""
        
        base_size = 100 if is_shorts else 90
        
        return f"""
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ReviewTitle,TmonMonsori,{int(base_size * 1.2)},&H00FFD700,&H00FFFFFF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,5,20,20,50,1
Style: ReviewKor,Noto Sans CJK KR,{base_size},&H00FFFFFF,&H00FFFFFF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,20,20,100,1
Style: ReviewEng,Arial,{int(base_size * 0.9)},&H00FFFF00,&H00FFFFFF,&H80000000,&H80000000,0,0,0,0,100,100,0,0,1,3,2,5,20,20,200,1
"""
    
    def _create_title_event(self, text: str, start: float, end: float) -> str:
        """타이틀 이벤트 생성 (페이드 + 스케일)"""
        start_time = self._format_time(start)
        end_time = self._format_time(end)
        
        # 페이드인 + 확대 효과
        effect = "{\\fad(500,500)\\t(0,500,\\fscx120\\fscy120)\\t(1500,2000,\\fscx100\\fscy100)}"
        
        return f"Dialogue: 0,{start_time},{end_time},ReviewTitle,,0,0,0,,{effect}{text}"
    
    def _create_text_event(self, text: str, start: float, end: float, 
                          style: str, fade_in: bool = False, slide: bool = False) -> str:
        """텍스트 이벤트 생성"""
        start_time = self._format_time(start)
        end_time = self._format_time(end)
        
        effects = []
        
        if fade_in:
            effects.append("\\fad(300,300)")
        
        if slide:
            # 오른쪽에서 슬라이드
            effects.append("\\move(1920,0,-100,0,0,300)")
        
        effect_str = "{" + "".join(effects) + "}" if effects else ""
        
        return f"Dialogue: 0,{start_time},{end_time},{style},,0,0,0,,{effect_str}{text}"
    
    async def _create_merged_tts(self, clips_data: List[Dict]) -> str:
        """TTS 생성 및 병합"""
        temp_files = []
        concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        
        try:
            # 타이틀 TTS
            title_tts = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            title_tts.close()
            await self.tts_generator.generate_tts_async("Speed Review", title_tts.name)
            temp_files.append(title_tts.name)
            concat_file.write(f"file '{title_tts.name}'\n")
            
            # 무음 구간 (0.5초)
            silence = self._create_silence(0.5)
            temp_files.append(silence)
            concat_file.write(f"file '{silence}'\n")
            
            # 각 클립 TTS
            for clip in clips_data:
                # 영어 TTS
                eng_tts = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                eng_tts.close()
                await self.tts_generator.generate_tts_async(clip['text_eng'], eng_tts.name)
                temp_files.append(eng_tts.name)
                concat_file.write(f"file '{eng_tts.name}'\n")
                
                # 클립 간 무음 (0.5초)
                silence = self._create_silence(0.5)
                temp_files.append(silence)
                concat_file.write(f"file '{silence}'\n")
            
            concat_file.close()
            
            # 오디오 병합
            output_audio = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            output_audio.close()
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c', 'copy',
                output_audio.name
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            return output_audio.name
            
        finally:
            # 임시 파일 정리
            concat_file.close()
            os.unlink(concat_file.name)
            for f in temp_files:
                if os.path.exists(f):
                    os.unlink(f)
    
    async def _prepare_background(self, media_path: str, width: int, height: int, 
                                 audio_file: str) -> str:
        """배경 비디오 준비 (원본을 흐리게 + 그라데이션)"""
        
        # 오디오 길이 확인
        duration = await self._get_audio_duration(audio_file)
        
        temp_bg = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_bg.close()
        
        # FFmpeg 복잡한 필터 체인
        filter_complex = [
            # 1. 입력 비디오 스케일 및 크롭
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[scaled]",
            
            # 2. 블러 효과
            "[scaled]boxblur=20:5[blurred]",
            
            # 3. 어둡게 처리
            "[blurred]colorchannelmixer=aa=0.3[darkened]",
            
            # 4. 상하단 그라데이션 오버레이
            f"color=black@0.8:s={width}x{int(height*0.3)}[topgrad]",
            f"color=black@0.8:s={width}x{int(height*0.3)}[botgrad]",
            "[darkened][topgrad]overlay=0:0[withtop]",
            f"[withtop][botgrad]overlay=0:{height - int(height*0.3)}[final]",
            
            # 5. 비네팅 효과
            "[final]vignette=angle=PI/4:mode=backward[output]"
        ]
        
        cmd = [
            'ffmpeg', '-y',
            '-i', media_path,
            '-filter_complex', ';'.join(filter_complex),
            '-map', '[output]',
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            temp_bg.name
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        return temp_bg.name
    
    async def _compose_final_video(self, background: str, ass_file: str, 
                                  audio_file: str, output_path: str,
                                  width: int, height: int) -> bool:
        """최종 비디오 합성"""
        try:
            # ASS 자막 필터
            ass_filter = f"ass='{ass_file}'"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', background,
                '-i', audio_file,
                '-filter_complex', ass_filter,
                '-map', '0:v',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '20',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',  # 오디오와 비디오 중 짧은 쪽에 맞춤
                '-movflags', '+faststart',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg compose error: {result.stderr}")
                return False
            
            logger.info(f"Review clip created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error composing video: {e}")
            return False
    
    def _create_silence(self, duration: float) -> str:
        """무음 생성"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_file.close()
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=stereo:d={duration}',
            '-c:a', 'mp3',
            temp_file.name
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return temp_file.name
    
    async def _get_audio_duration(self, audio_file: str) -> float:
        """오디오 길이 확인"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return float(result.stdout.strip())
        return 10.0  # 기본값
    
    def _format_time(self, seconds: float) -> str:
        """초를 ASS 시간 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def _generate_ass_header(self, is_shorts: bool) -> str:
        """ASS 헤더 생성"""
        width = 1080 if is_shorts else 1920
        height = 1920 if is_shorts else 1080
        
        return f"""[Script Info]
Title: Review Clip
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
Timer: 100.0000
WrapStyle: 0
"""
    
    async def create_simple_review_clip(self, clips_data: List[Dict],
                                        output_path: str,
                                        title: str = "Speed Review",
                                        template_number: int = 11,
                                        with_tts: bool = False) -> bool:
        """단순한 검은 배경 리뷰 클립 생성 (정지화면)"""
        try:
            # 쇼츠 여부 확인
            is_shorts = template_number in [11, 12, 13]
            width = 1080 if is_shorts else 1920
            height = 1920 if is_shorts else 1080
            
            # TTS 오디오 생성 (선택적)
            audio_file = None
            if with_tts:
                audio_file = await self._create_merged_tts(clips_data)
                duration = await self._get_audio_duration(audio_file)
            else:
                # TTS 없이 고정 시간 사용 (각 클립당 3초)
                duration = 2 + len(clips_data) * 3  # 타이틀 2초 + 클립들
            
            # 개별 클립 비디오 생성
            clip_videos = []
            temp_files = []
            
            # 타이틀 클립 (2초)
            title_clip = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            title_clip.close()
            temp_files.append(title_clip.name)
            
            cmd_title = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=black:s={width}x{height}:d=2',
                '-vf', f"drawtext=text='{title.replace(':', '\\:').replace(chr(39), chr(92)+chr(39))}':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=100:fontcolor=#FFD700:x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '20',
                title_clip.name
            ]
            subprocess.run(cmd_title, check=True, capture_output=True)
            clip_videos.append(title_clip.name)
            
            # 각 클립 비디오 생성
            clip_duration = (duration - 2) / len(clips_data) if clips_data else 3.0
            
            for idx, clip_data in enumerate(clips_data):
                clip_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                clip_file.close()
                temp_files.append(clip_file.name)
                
                text_kor = clip_data['text_kor'].replace(":", "\\:").replace("'", "\\'")
                text_eng = clip_data['text_eng'].replace(":", "\\:").replace("'", "\\'")
                
                cmd_clip = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi',
                    '-i', f'color=c=black:s={width}x{height}:d={clip_duration}',
                    '-vf', (
                        f"drawbox=x=0:y={(height//2)-150}:w={width}:h=300:color=black@0.8:t=fill,"
                        f"drawtext=text='{text_kor}':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=60:"
                        f"fontcolor=white:x=(w-text_w)/2:y={(height//2)-80},"
                        f"drawtext=text='{text_eng}':fontfile='/home/kang/.fonts/TmonMonsori.ttf':fontsize=50:"
                        f"fontcolor=#FFD700:x=(w-text_w)/2:y={(height//2)+20}"
                    ),
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '20',
                    clip_file.name
                ]
                subprocess.run(cmd_clip, check=True, capture_output=True)
                clip_videos.append(clip_file.name)
            
            # concat 리스트 파일 생성
            concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            temp_files.append(concat_file.name)
            for video in clip_videos:
                concat_file.write(f"file '{video}'\n")
            concat_file.close()
            
            # 비디오 합치고 오디오 추가 (TTS 있을 때만)
            if with_tts and audio_file:
                cmd_final = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file.name,
                    '-i', audio_file,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest',
                    '-movflags', '+faststart',
                    output_path
                ]
            else:
                # TTS 없이 비디오만
                cmd_final = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file.name,
                    '-c:v', 'copy',
                    '-movflags', '+faststart',
                    output_path
                ]
            
            result = subprocess.run(cmd_final, capture_output=True, text=True)
            
            # 임시 파일 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            if audio_file and os.path.exists(audio_file):
                os.unlink(audio_file)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            logger.info(f"Simple review clip created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating simple review clip: {e}", exc_info=True)
            return False