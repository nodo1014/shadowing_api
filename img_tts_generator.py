"""
Image + TTS Video Generator - 이미지와 TTS를 결합한 비디오 생성기
Still Image + Text + TTS를 조합한 다목적 비디오 클립 생성 모듈

활용 예시:
- 스터디 클립 (영상 캡처 + 학습 문장)
- 썸네일 동영상 (이미지 + 제목)
- 설명 영상 (슬라이드 + 나레이션)
- 인트로/아웃트로
- 공지사항
- 명언/격언 영상
"""
import os
import tempfile
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Union
from edge_tts_util import EdgeTTSGenerator

logger = logging.getLogger(__name__)


class ImgTTSGenerator:
    """정지 이미지 + TTS 비디오 생성기"""
    
    def __init__(self):
        self.default_font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/home/kang/.fonts/NotoSansCJK-Bold.ttc",
            "/home/kang/.fonts/NotoSansCJK.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        ]
        
    async def create_video(
        self,
        # 이미지 소스 (하나만 제공)
        image_path: Optional[str] = None,           # 기존 이미지 파일
        video_frame: Optional[Dict] = None,          # 비디오에서 프레임 추출 정보
        color_background: Optional[str] = None,      # 단색 배경
        
        # 텍스트 & 오디오
        texts: List[Dict[str, Union[str, Dict]]] = None,  # 텍스트 정보 리스트
        tts_config: Optional[Dict] = None,           # TTS 설정
        audio_source: Optional[Dict] = None,         # 오디오 소스 (원본 추출 또는 파일)
        
        # 출력 설정
        output_path: str = "output.mp4",
        duration: Optional[float] = None,            # None이면 오디오 길이에 맞춤
        resolution: tuple = (1920, 1080),            # (width, height)
        
        # 스타일 옵션
        style_preset: Optional[str] = None,          # 미리 정의된 스타일
        
        # 추가 옵션
        add_silence: float = 0.0                     # 끝에 추가할 무음 길이
    ) -> bool:
        """
        정지 이미지 + TTS 비디오 생성
        
        Args:
            image_path: 이미지 파일 경로
            video_frame: {'path': 비디오경로, 'time': 추출시간, 'crop': 크롭필터}
            color_background: 배경색 (예: 'black', '#FF0000')
            texts: [{'text': 텍스트, 'style': {폰트, 크기, 색상, 위치 등}}]
            tts_config: {'text': TTS텍스트, 'voice': 음성, 'rate': 속도}
            audio_source: {'type': 'extract'/'file', 'path': 파일경로, 'start': 시작, 'end': 종료}
            output_path: 출력 파일 경로
            duration: 비디오 길이 (None이면 오디오 기준)
            resolution: 해상도
            style_preset: 'shorts', 'presentation', 'subtitle' 등
        """
        try:
            width, height = resolution
            
            # 1. 배경 이미지 준비
            background = await self._prepare_background(
                image_path, video_frame, color_background, resolution
            )
            if not background:
                logger.error("Failed to prepare background")
                return False
            
            # 2. 오디오 준비 (TTS 또는 원본 추출)
            audio_file = None
            if audio_source:
                # 원본 오디오 사용
                audio_file = await self._prepare_audio_source(audio_source)
                if audio_file and not duration:
                    duration = await self._get_audio_duration(audio_file)
            elif tts_config:
                # TTS 생성
                audio_file = await self._generate_tts(tts_config)
                if audio_file and not duration:
                    duration = await self._get_audio_duration(audio_file)
            
            if not duration:
                duration = 5.0  # 기본 5초
            
            # 무음 추가
            if add_silence > 0:
                duration += add_silence
            
            # 3. 스타일 프리셋 적용
            if style_preset and texts:
                texts = self._apply_style_preset(texts, style_preset, resolution)
            
            # 4. 텍스트 필터 생성
            text_filter = ""
            if texts:
                text_filter = self._create_text_filters(texts, resolution)
            
            # 5. FFmpeg로 비디오 생성
            success = await self._create_video_with_ffmpeg(
                background, audio_file, text_filter, output_path, duration, resolution, add_silence
            )
            
            # 6. 정리
            if background != image_path and os.path.exists(background):
                os.unlink(background)
            if audio_file and os.path.exists(audio_file):
                os.unlink(audio_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating still+TTS video: {e}", exc_info=True)
            return False
    
    async def _prepare_background(
        self, 
        image_path: Optional[str],
        video_frame: Optional[Dict],
        color_background: Optional[str],
        resolution: tuple
    ) -> Optional[str]:
        """배경 이미지 준비"""
        width, height = resolution
        
        if image_path and os.path.exists(image_path):
            # 기존 이미지 사용 (리사이즈 필요시)
            return image_path
            
        elif video_frame:
            # 비디오에서 프레임 추출
            return await self._extract_video_frame(
                video_frame['path'],
                video_frame.get('time', 0),
                video_frame.get('crop'),
                resolution
            )
            
        elif color_background:
            # 단색 배경 생성
            temp_bg = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_bg.close()
            
            color = color_background if color_background.startswith('#') else color_background
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c={color}:s={width}x{height}:d=1',
                '-frames:v', '1',
                temp_bg.name
            ]
            
            result = await self._run_async(cmd)
            if result.returncode == 0:
                return temp_bg.name
            else:
                os.unlink(temp_bg.name)
                return None
        
        return None
    
    async def _extract_video_frame(
        self, 
        video_path: str,
        time: float,
        crop_filter: Optional[str],
        resolution: tuple
    ) -> Optional[str]:
        """비디오에서 프레임 추출"""
        temp_frame = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_frame.close()
        
        width, height = resolution
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(time),
            '-i', video_path,
            '-frames:v', '1'
        ]
        
        # 크롭/스케일 필터
        if crop_filter:
            cmd.extend(['-vf', crop_filter])
        else:
            # 기본 스케일
            cmd.extend(['-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2'])
        
        cmd.extend(['-q:v', '2', temp_frame.name])
        
        result = await self._run_async(cmd)
        if result.returncode == 0:
            return temp_frame.name
        else:
            os.unlink(temp_frame.name)
            return None
    
    async def _prepare_audio_source(self, audio_source: Dict) -> Optional[str]:
        """오디오 소스 준비 (파일 또는 비디오에서 추출)"""
        audio_type = audio_source.get('type', 'file')
        
        if audio_type == 'file' and 'path' in audio_source:
            # 기존 오디오 파일 사용
            if os.path.exists(audio_source['path']):
                return audio_source['path']
                
        elif audio_type == 'extract':
            # 비디오에서 오디오 추출
            video_path = audio_source.get('path')
            start_time = audio_source.get('start', 0)
            end_time = audio_source.get('end')
            
            if video_path and os.path.exists(video_path):
                return await self._extract_audio_from_video(
                    video_path, start_time, end_time
                )
        
        return None
    
    async def _extract_audio_from_video(
        self, 
        video_path: str, 
        start_time: float = 0, 
        end_time: Optional[float] = None
    ) -> Optional[str]:
        """비디오에서 오디오 추출"""
        temp_audio = tempfile.NamedTemporaryFile(suffix='.aac', delete=False)
        temp_audio.close()
        
        cmd = ['ffmpeg', '-y']
        
        # 시작 시간
        if start_time > 0:
            cmd.extend(['-ss', str(start_time)])
            
        cmd.extend(['-i', video_path])
        
        # 종료 시간 (duration으로 변환)
        if end_time and end_time > start_time:
            duration = end_time - start_time
            cmd.extend(['-t', str(duration)])
        
        # 오디오만 추출
        cmd.extend([
            '-vn',  # 비디오 없음
            '-acodec', 'copy',  # 오디오 코덱 복사 (재인코딩 없음)
            temp_audio.name
        ])
        
        result = await self._run_async(cmd)
        if result.returncode == 0:
            logger.info(f"Audio extracted: {start_time}s - {end_time}s")
            return temp_audio.name
        else:
            logger.error(f"Failed to extract audio: {result.stderr}")
            os.unlink(temp_audio.name)
            return None
    
    async def _generate_tts(self, tts_config: Dict) -> Optional[str]:
        """TTS 생성"""
        temp_audio = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_audio.close()
        
        text = tts_config.get('text', '')
        voice = tts_config.get('voice', 'en-US-AriaNeural')
        rate = tts_config.get('rate', '+0%')
        pitch = tts_config.get('pitch', '+0Hz')
        
        generator = EdgeTTSGenerator(voice=voice, rate=rate, pitch=pitch)
        
        if await generator.generate_tts_async(text, temp_audio.name):
            return temp_audio.name
        else:
            os.unlink(temp_audio.name)
            return None
    
    def _create_text_filters(self, texts: List[Dict], resolution: tuple) -> str:
        """텍스트 필터 생성"""
        filters = []
        
        for text_info in texts:
            text = text_info.get('text', '')
            style = text_info.get('style', {})
            
            # 폰트 찾기
            font_file = self._find_font(style.get('font_path'))
            
            # 기본 스타일 값
            fontsize = style.get('fontsize', 60)
            fontcolor = style.get('fontcolor', 'white')
            borderw = style.get('borderw', 3)
            bordercolor = style.get('bordercolor', 'black')
            x = style.get('x', '(w-text_w)/2')  # 중앙
            y = style.get('y', '(h-text_h)/2')  # 중앙
            
            # 시간 설정 (특정 시간에만 표시)
            enable = style.get('enable', '')
            
            # drawtext 필터 구성
            filter_str = f"drawtext=text='{self._escape_text(text)}':fontfile='{font_file}':"
            filter_str += f"fontsize={fontsize}:fontcolor={fontcolor}:"
            filter_str += f"borderw={borderw}:bordercolor={bordercolor}:"
            filter_str += f"x={x}:y={y}"
            
            if enable:
                filter_str += f":enable='{enable}'"
            
            filters.append(filter_str)
        
        return ','.join(filters) if filters else ''
    
    def _apply_style_preset(self, texts: List[Dict], preset: str, resolution: tuple) -> List[Dict]:
        """스타일 프리셋 적용"""
        width, height = resolution
        
        if preset == 'shorts':
            # 쇼츠용 스타일 - 정사각형 크롭 영역 안에 자막 배치
            # 실제 비디오는 420~1500px 영역에 표시됨
            for i, text_info in enumerate(texts):
                if i == 0:  # 첫 번째 텍스트 (한글)
                    text_info['style'] = text_info.get('style', {})
                    text_info['style'].update({
                        'fontsize': 54,
                        'fontcolor': '#FFD700',
                        'borderw': 5,
                        'x': '(w-text_w)/2',
                        'y': '1280'  # 실제 비디오 영역 내 하단 (1500-220)
                    })
                elif i == 1:  # 두 번째 텍스트 (영어)
                    text_info['style'] = text_info.get('style', {})
                    text_info['style'].update({
                        'fontsize': 60,
                        'fontcolor': 'white',
                        'borderw': 5,
                        'x': '(w-text_w)/2',
                        'y': '1140'  # 실제 비디오 영역 내 (1500-360)
                    })
                    
        elif preset == 'presentation':
            # 프레젠테이션 스타일 (제목 크게)
            for i, text_info in enumerate(texts):
                if i == 0:  # 제목
                    text_info['style'] = text_info.get('style', {})
                    text_info['style'].update({
                        'fontsize': 100,
                        'fontcolor': 'white',
                        'borderw': 4,
                        'x': '(w-text_w)/2',
                        'y': 'h/2-200'
                    })
                else:  # 부제목
                    text_info['style'] = text_info.get('style', {})
                    text_info['style'].update({
                        'fontsize': 60,
                        'fontcolor': '#CCCCCC',
                        'borderw': 3,
                        'x': '(w-text_w)/2',
                        'y': f'h/2+{(i-1)*80}'
                    })
                    
        elif preset == 'subtitle':
            # 일반 자막 스타일
            for text_info in texts:
                text_info['style'] = text_info.get('style', {})
                text_info['style'].update({
                    'fontsize': 40,
                    'fontcolor': 'white',
                    'borderw': 2,
                    'x': '(w-text_w)/2',
                    'y': 'h-100'
                })
        
        return texts
    
    async def _create_video_with_ffmpeg(
        self,
        background: str,
        audio_file: Optional[str],
        text_filter: str,
        output_path: str,
        duration: float,
        resolution: tuple,
        add_silence: float = 0.0
    ) -> bool:
        """FFmpeg로 최종 비디오 생성"""
        width, height = resolution
        
        cmd = ['ffmpeg', '-y']
        
        # 입력: 배경 이미지 (루프)
        cmd.extend(['-loop', '1', '-i', background])
        
        # 입력: 오디오 (있는 경우)
        if audio_file:
            cmd.extend(['-i', audio_file])
            # 무음 추가가 필요한 경우
            if add_silence > 0:
                cmd.extend([
                    '-f', 'lavfi',
                    '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={add_silence}'
                ])
        else:
            # 무음 생성
            cmd.extend([
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100'
            ])
        
        # 길이 설정
        cmd.extend(['-t', str(duration)])
        
        # 비디오 필터는 텍스트 필터만 사용
        video_filter_str = text_filter if text_filter else None
        
        # 필터 설정
        if audio_file and add_silence > 0:
            # 오디오 concat과 비디오 필터를 함께 처리
            filter_complex = '[1:a][2:a]concat=n=2:v=0:a=1[outa]'
            if video_filter_str:
                filter_complex = f'{filter_complex};[0:v]{video_filter_str}[outv]'
                cmd.extend([
                    '-filter_complex', filter_complex,
                    '-map', '[outv]',
                    '-map', '[outa]'
                ])
            else:
                cmd.extend([
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[outa]'
                ])
        else:
            # 비디오 필터만
            if video_filter_str:
                cmd.extend(['-vf', video_filter_str])
            # 기본 매핑
            cmd.extend(['-map', '0:v'])
            if audio_file:
                cmd.extend(['-map', '1:a'])
            else:
                cmd.extend(['-map', '1:a'])
        
        # 인코딩 설정
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '22',
            '-profile:v', 'high',
            '-level', '4.1',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ])
        
        result = await self._run_async(cmd)
        return result.returncode == 0
    
    def _find_font(self, custom_path: Optional[str] = None) -> str:
        """사용 가능한 폰트 찾기"""
        if custom_path and os.path.exists(custom_path):
            return custom_path
            
        for path in self.default_font_paths:
            if os.path.exists(path):
                return path
                
        return "NanumGothic"  # 폴백
    
    def _escape_text(self, text: str) -> str:
        """FFmpeg drawtext용 텍스트 이스케이프"""
        text = text.replace('\\', '\\\\')
        text = text.replace(':', '\\:')
        text = text.replace("'", "\\'")
        text = text.replace('"', '\\"')
        text = text.replace('%', '\\%')
        text = text.replace(',', '\\,')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('=', '\\=')
        return text
    
    async def _get_audio_duration(self, audio_file: str) -> float:
        """오디오 길이 확인"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ]
        
        result = await self._run_async(cmd)
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except:
                pass
        return 5.0
    
    async def _run_async(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """비동기 명령 실행"""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return subprocess.CompletedProcess(
            cmd, process.returncode,
            stdout.decode() if stdout else '',
            stderr.decode() if stderr else ''
        )


# 사용 예시
async def example_usage():
    """사용 예시"""
    generator = ImgTTSGenerator()
    
    # 1. 비디오 프레임 + TTS (스터디 클립)
    await generator.create_video(
        video_frame={
            'path': '/path/to/video.mp4',
            'time': 50.5,
            'crop': "crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        },
        texts=[
            {'text': '너희는 헌터가 될 거야', 'style': {}},
            {'text': 'You will be Hunters.', 'style': {}}
        ],
        tts_config={
            'text': 'You will be Hunters.',
            'voice': 'en-US-AriaNeural',
            'rate': '-10%'
        },
        output_path='study_clip.mp4',
        resolution=(1080, 1920),
        style_preset='shorts'
    )
    
    # 2. 이미지 + TTS (설명 영상)
    await generator.create_video(
        image_path='/path/to/image.jpg',
        texts=[
            {'text': 'Python Programming', 'style': {'fontsize': 100, 'y': 100}},
            {'text': 'Chapter 1: Introduction', 'style': {'fontsize': 60, 'y': 250}}
        ],
        tts_config={
            'text': 'Welcome to Python programming course.',
            'voice': 'en-US-AriaNeural'
        },
        output_path='intro.mp4',
        style_preset='presentation'
    )
    
    # 3. 단색 배경 + 텍스트 애니메이션
    await generator.create_video(
        color_background='black',
        texts=[
            {
                'text': 'Welcome', 
                'style': {'enable': "between(t,0,2)"}
            },
            {
                'text': 'To Our Channel',
                'style': {'enable': "between(t,2,4)"}
            }
        ],
        duration=5,
        output_path='intro_animated.mp4'
    )
    
    # 4. 비디오 프레임 + 원본 오디오 (가사 표시)
    await generator.create_video(
        video_frame={
            'path': '/path/to/music_video.mp4',
            'time': 60.0,  # 1분 지점의 프레임
        },
        texts=[
            {'text': '♪ Fly me to the moon ♪', 'style': {'fontsize': 80}},
            {'text': '달로 날 데려가 줘', 'style': {'fontsize': 60}}
        ],
        audio_source={
            'type': 'extract',
            'path': '/path/to/music_video.mp4',
            'start': 60.0,
            'end': 65.0
        },
        output_path='lyrics_clip.mp4',
        style_preset='subtitle'
    )
    
    # 5. 이미지 + 팟캐스트 오디오 파일
    await generator.create_video(
        image_path='/path/to/podcast_cover.jpg',
        texts=[
            {'text': 'Episode 10: AI Revolution', 'style': {'fontsize': 100}},
            {'text': 'Tech Podcast', 'style': {'fontsize': 60, 'fontcolor': '#FFD700'}}
        ],
        audio_source={
            'type': 'file',
            'path': '/path/to/podcast_episode_10.mp3'
        },
        output_path='podcast_visual.mp4',
        style_preset='presentation'
    )


if __name__ == "__main__":
    asyncio.run(example_usage())