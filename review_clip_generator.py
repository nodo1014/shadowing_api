"""
Review clip generator for YouTube Shorts
YouTube 쇼츠용 복습 클립 생성기
"""
import os
import tempfile
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from edge_tts_util import EdgeTTSGenerator

logger = logging.getLogger(__name__)


class ReviewClipGenerator:
    """복습 클립 생성기"""
    
    def __init__(self):
        # 영어는 Aria 음성, 속도 약간 느리게 (-10%)
        self.tts_generator = EdgeTTSGenerator(voice='en-US-AriaNeural', rate='-10%')
        
    async def create_review_clip(self, clips_data: List[Dict], output_path: str,
                                title: str = "스피드 복습", template_number: int = 11,
                                video_path: Optional[str] = None, 
                                clip_timestamps: Optional[List[Tuple[float, float]]] = None) -> bool:
        """복습 클립 생성
        
        Args:
            clips_data: 클립 데이터 리스트 [{text_eng, text_kor}, ...]
            output_path: 출력 파일 경로
            title: 복습 제목
            template_number: 템플릿 번호 (쇼츠 여부 판단용)
            video_path: 원본 비디오 경로 (정지 프레임 추출용)
            clip_timestamps: 각 클립의 시작/종료 시간
        """
        self.video_path = video_path
        self.clip_timestamps = clip_timestamps
        tts_files = []  # finally 블록에서 사용하므로 try 밖에서 초기화
        try:
            logger.info(f"Starting review clip creation for {len(clips_data)} clips")
            # 쇼츠 여부 확인
            is_shorts = template_number in [11, 12, 13]
            width = 1080 if is_shorts else 1920
            height = 1920 if is_shorts else 1080
            
            # TTS 생성
            logger.info("Generating TTS for review clips...")
            
            for idx, clip in enumerate(clips_data):
                logger.info(f"Generating TTS for clip {idx+1}/{len(clips_data)}: {clip['text_eng'][:30]}...")
                # 영어 TTS (선희 음성으로)
                eng_tts_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                eng_tts_file.close()
                
                if await self.tts_generator.generate_tts_async(
                    clip['text_eng'], 
                    eng_tts_file.name
                ):
                    tts_files.append({
                        'clip_idx': idx,
                        'tts_file': eng_tts_file.name,
                        'text_kor': clip['text_kor'],
                        'text_eng': clip['text_eng']
                    })
            
            # 비디오 생성
            return await self._create_review_video(
                tts_files, output_path, title, width, height
            )
            
        except Exception as e:
            logger.error(f"Error creating review clip: {e}", exc_info=True)
            return False
        finally:
            # 임시 파일 정리
            for tts_data in tts_files:
                if os.path.exists(tts_data['tts_file']):
                    os.unlink(tts_data['tts_file'])
    
    async def _create_review_video(self, tts_files: List[Dict], output_path: str,
                                  title: str, width: int, height: int) -> bool:
        """복습 비디오 생성"""
        freeze_frames = []  # 정지 프레임 추적
        try:
            # 크롭 필터 결정 (쇼츠이면 정사각형 크롭)
            is_shorts = width == 1080
            if is_shorts:
                crop_filter = "crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            else:
                crop_filter = None
            
            # 개별 클립 생성
            temp_clips = []
            
            for idx, tts_data in enumerate(tts_files):
                temp_clip = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_clip.close()
                temp_clips.append(temp_clip.name)
                
                # 원본 비디오에서 정지 프레임 추출 (제공된 경우)
                freeze_frame = None
                if self.video_path and self.clip_timestamps and idx < len(self.clip_timestamps):
                    start_time, end_time = self.clip_timestamps[idx]
                    freeze_time = (start_time + end_time) / 2  # 클립 중간 시점
                    logger.info(f"Extracting freeze frame at {freeze_time:.1f}s from {self.video_path}")
                    freeze_frame = await self._extract_freeze_frame(
                        self.video_path, freeze_time, crop_filter
                    )
                    if freeze_frame:
                        logger.info(f"Freeze frame extracted: {freeze_frame}")
                        freeze_frames.append(freeze_frame)
                    else:
                        logger.warning(f"Failed to extract freeze frame for clip {idx+1}")
                
                # drawtext로 텍스트 표시 + TTS 오디오
                drawtext_filter = self._create_drawtext_filter(
                    tts_data['text_kor'], 
                    tts_data['text_eng'],
                    idx,
                    width,
                    height
                )
                
                # 오디오 길이 확인
                duration = await self._get_audio_duration(tts_data['tts_file'])
                if duration < 2.0:
                    duration = 2.0  # 최소 2초
                elif duration > 5.0:
                    duration = 5.0  # 최대 5초로 제한 (메모리 절약)
                
                # FFmpeg 명령 (템플릿 클립과 동일한 설정)
                if freeze_frame and os.path.exists(freeze_frame):
                    # 정지 프레임을 배경으로 사용
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1', '-i', freeze_frame,
                        '-i', tts_data['tts_file'],
                        '-t', str(duration),
                        '-vf', drawtext_filter,
                        '-c:v', 'libx264',
                        '-preset', 'medium',
                        '-crf', '16',
                        '-profile:v', 'high',
                        '-level', '4.1',
                        '-pix_fmt', 'yuv420p',
                        '-tune', 'film',
                        '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-shortest',
                        '-movflags', '+faststart',
                        temp_clip.name
                    ]
                else:
                    # 기본 검은 배경
                    cmd = [
                        'ffmpeg', '-y',
                        '-f', 'lavfi',
                        '-i', f'color=c=black:s={width}x{height}:d={duration}',
                        '-i', tts_data['tts_file'],
                        '-vf', drawtext_filter,
                        '-c:v', 'libx264',
                        '-preset', 'medium',
                        '-crf', '16',
                        '-profile:v', 'high',
                        '-level', '4.1',
                        '-pix_fmt', 'yuv420p',
                        '-tune', 'film',
                        '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-shortest',
                        '-movflags', '+faststart',
                        temp_clip.name
                    ]
                
                logger.debug(f"FFmpeg command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"FFmpeg error: {result.stderr}")
                    return False
                else:
                    logger.info(f"Created clip {idx+1} with TTS audio")
            
            # 제목 클립 추가
            title_clip = await self._create_title_clip(title, width, height)
            if title_clip:
                temp_clips.insert(0, title_clip)
            
            # 클립 연결
            return await self._concat_clips(temp_clips, output_path)
            
        except Exception as e:
            logger.error(f"Error creating review video: {e}")
            return False
        finally:
            # 임시 파일 정리
            for clip in temp_clips:
                if os.path.exists(clip):
                    os.unlink(clip)
            # 정지 프레임 정리
            for frame in freeze_frames:
                if os.path.exists(frame):
                    os.unlink(frame)
    
    def _create_drawtext_filter(self, text_kor: str, text_eng: str, 
                               idx: int, width: int, height: int) -> str:
        """drawtext 필터 생성 - 템플릿과 동일한 폰트 로직 사용"""
        # NotoSans CJK 폰트 경로 (Bold 우선)
        font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",     # Bold 버전 우선
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Regular
            "/home/kang/.fonts/NotoSansCJK-Bold.ttc",
            "/home/kang/.fonts/NotoSansCJK.ttc",
            "/home/kang/.fonts/NotoSansCJKkr-hinted/NotoSansCJKkr-Bold.otf",
            "/home/kang/.fonts/NotoSansCJKkr-hinted/NotoSansCJKkr-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/home/kang/.fonts/NanumGothic.ttf",  # 폴백
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        ]
        
        font_file = None
        for path in font_paths:
            if os.path.exists(path):
                font_file = path
                logger.info(f"Using NotoSans font: {path}")
                break
        
        if not font_file:
            font_file = "NanumGothic"  # 한글 지원되는 기본 폰트
            logger.warning("NotoSans font not found, using fallback: NanumGothic")
        
        # 개선된 텍스트 이스케이프 함수
        def escape_drawtext(text: str) -> str:
            """
            drawtext용 안전한 텍스트 이스케이프
            FFmpeg drawtext 필터에서 특수 문자로 인식될 수 있는 모든 문자를 이스케이프
            """
            # 백슬래시를 가장 먼저 처리
            text = text.replace('\\', '\\\\')
            # drawtext에서 특수한 의미를 가지는 문자들 이스케이프
            text = text.replace(':', '\\:')
            text = text.replace("'", "\\'")
            text = text.replace('"', '\\"')
            text = text.replace('%', '\\%')
            text = text.replace(',', '\\,')
            text = text.replace('[', '\\[')
            text = text.replace(']', '\\]')
            text = text.replace('=', '\\=')
            return text
        
        text_kor = escape_drawtext(text_kor)
        text_eng = escape_drawtext(text_eng)
        
        # 코치 템플릿처럼 Y 위치 계산
        is_shorts = width == 1080  # 쇼츠 판별
        
        if is_shorts:
            # 쇼츠용 레이아웃
            base_y = height // 2 - 100
            korean_size = 80
            english_size = 60
            gap = 100
        else:
            # 일반 횡형식 레이아웃
            base_y = height // 2 - 60
            korean_size = 60
            english_size = 50
            gap = 80
        
        # 한국어 (위) - 두꺼운 테두리
        filter1 = (f"drawtext=text='{text_kor}':"
                  f"fontfile='{font_file}':fontsize={korean_size}:"
                  f"fontcolor=white:borderw=5:bordercolor=black:"
                  f"x=(w-text_w)/2:y={base_y}")
        
        # 영어 (아래) - 두꺼운 테두리
        filter2 = (f"drawtext=text='{text_eng}':"
                  f"fontfile='{font_file}':fontsize={english_size}:"
                  f"fontcolor=#CCCCCC:borderw=5:bordercolor=black:"
                  f"x=(w-text_w)/2:y={base_y + gap}")
        
        return f"{filter1},{filter2}"
    
    async def _get_audio_duration(self, audio_file: str) -> float:
        """오디오 파일 길이 확인"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except:
                pass
        return 3.0  # 기본값
    
    async def _create_title_clip(self, title: str, width: int, height: int) -> Optional[str]:
        """타이틀 클립 생성 - 템플릿 타이틀과 동일한 스타일"""
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_file.close()
            
            # NotoSans CJK 폰트 경로 (Bold 우선)
            font_paths = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",     # Bold 버전 우선
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Regular
                "/home/kang/.fonts/NotoSansCJK-Bold.ttc",
                "/home/kang/.fonts/NotoSansCJK.ttc",
                "/home/kang/.fonts/NotoSansCJKkr-hinted/NotoSansCJKkr-Bold.otf",
                "/home/kang/.fonts/NotoSansCJKkr-hinted/NotoSansCJKkr-Regular.otf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/home/kang/.fonts/NanumGothic.ttf",  # 폴백
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
            ]
            
            font_file = None
            for path in font_paths:
                if os.path.exists(path):
                    font_file = path
                    logger.info(f"Title clip using NotoSans font: {path}")
                    break
                    
            if not font_file:
                font_file = "NanumGothic"
                logger.warning("Title: NotoSans font not found, using fallback: NanumGothic")
            
            title = title.replace(":", "\\:").replace("'", "\\'")
            
            # 쇼츠 판별
            is_shorts = width == 1080
            
            if is_shorts:
                # 쇼츠용 타이틀 (템플릿처럼 120pt 흰색)
                fontsize = 120
                fontcolor = "white"
            else:
                # 일반 횡형식 타이틀
                fontsize = 80
                fontcolor = "white"
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=black:s={width}x{height}:d=2',
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-vf', f"drawtext=text='{title}':fontfile='{font_file}':"
                       f"fontsize={fontsize}:fontcolor={fontcolor}:borderw=5:bordercolor=black:"
                       f"x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',  # 템플릿과 동일한 CRF
                '-profile:v', 'high',
                '-level', '4.1',
                '-pix_fmt', 'yuv420p',
                '-tune', 'film',
                '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                temp_file.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return temp_file.name
                
        except Exception as e:
            logger.error(f"Error creating title clip: {e}")
        
        return None
    
    async def _extract_freeze_frame(self, video_path: str, time: float, 
                                   crop_filter: Optional[str] = None) -> Optional[str]:
        """비디오에서 정지 프레임 추출"""
        try:
            temp_frame = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_frame.close()
            
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(time),
                '-i', video_path,
                '-frames:v', '1',
            ]
            
            if crop_filter:
                cmd.extend(['-vf', crop_filter])
            
            cmd.extend(['-q:v', '2', temp_frame.name])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return temp_frame.name
            else:
                logger.error(f"Failed to extract freeze frame: {result.stderr}")
                if os.path.exists(temp_frame.name):
                    os.unlink(temp_frame.name)
                    
        except Exception as e:
            logger.error(f"Error extracting freeze frame: {e}")
        
        return None
    
    async def _concat_clips(self, clips: List[str], output_path: str) -> bool:
        """Filter_complex를 사용한 안정적 클립 병합"""
        try:
            if len(clips) == 0:
                logger.error("No clips to concatenate")
                return False
                
            if len(clips) == 1:
                # 단일 클립인 경우 복사만
                cmd = ['ffmpeg', '-y', '-i', clips[0], '-c', 'copy', output_path]
            else:
                # 다중 클립 filter_complex 병합
                inputs = []
                for clip in clips:
                    inputs.extend(['-i', clip])
                
                # filter_complex 구성
                filter_parts = []
                for i in range(len(clips)):
                    filter_parts.append(f"[{i}:v][{i}:a]")
                
                filter_complex = f"{''.join(filter_parts)}concat=n={len(clips)}:v=1:a=1[outv][outa]"
                
                cmd = [
                    'ffmpeg', '-y'
                ] + inputs + [
                    '-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
                    '-movflags', '+faststart',
                    output_path
                ]
            
            logger.debug(f"Concat command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg concat error: {result.stderr}")
                return False
                
            logger.info(f"Successfully concatenated {len(clips)} clips to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error concatenating clips: {e}", exc_info=True)
            return False