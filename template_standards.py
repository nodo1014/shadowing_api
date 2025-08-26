"""
Template Standards Module
템플릿 시스템을 위한 표준화된 비디오/오디오 처리 함수들

이 모듈의 목적:
1. 모든 템플릿에서 동일한 방식으로 무음, 프리즈 프레임 생성
2. 오디오 포맷 불일치 문제 방지
3. 안정적인 병합 보장
"""

import os
import time
import subprocess
import tempfile
import logging
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class TemplateStandards:
    """템플릿 시스템 표준 처리 함수"""
    
    # 표준 설정값들
    STANDARD_VIDEO_WIDTH = 1920
    STANDARD_VIDEO_HEIGHT = 1080
    STANDARD_VIDEO_CRF = 22
    STANDARD_VIDEO_PRESET = 'medium'
    STANDARD_VIDEO_CODEC = 'libx264'
    STANDARD_PIX_FMT = 'yuv420p'
    
    # 무음 생성용 표준 오디오 설정
    SILENCE_SAMPLE_RATE = 44100
    SILENCE_CHANNELS = 2
    SILENCE_CHANNEL_LAYOUT = 'stereo'
    
    # 최종 출력용 표준 오디오 설정
    OUTPUT_SAMPLE_RATE = 48000
    OUTPUT_CHANNELS = 2
    OUTPUT_AUDIO_BITRATE = '192k'
    
    @staticmethod
    def create_silence_wav(duration: float, output_path: Optional[str] = None) -> str:
        """
        표준 무음 WAV 파일 생성
        
        Args:
            duration: 무음 길이 (초)
            output_path: 출력 경로 (None이면 임시 파일)
            
        Returns:
            생성된 WAV 파일 경로
        """
        if output_path is None:
            output_path = f"/tmp/silence_{int(time.time() * 1000)}.wav"
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=channel_layout={TemplateStandards.SILENCE_CHANNEL_LAYOUT}:sample_rate={TemplateStandards.SILENCE_SAMPLE_RATE}',
            '-t', str(duration),
            '-acodec', 'pcm_s16le',
            '-ar', str(TemplateStandards.SILENCE_SAMPLE_RATE),
            '-ac', str(TemplateStandards.SILENCE_CHANNELS),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to create silence WAV: {result.stderr}")
            raise Exception(f"Silence generation failed: {result.stderr}")
        
        logger.debug(f"Created silence WAV: {output_path} ({duration}s)")
        return output_path
    
    @staticmethod
    def create_freeze_frame(video_path: str, frame_time: float, duration: float = 0.5, 
                          output_path: Optional[str] = None) -> str:
        """
        표준 프리즈 프레임 생성
        
        Args:
            video_path: 원본 비디오 경로
            frame_time: 프레임 추출 시간
            duration: 프리즈 프레임 길이
            output_path: 출력 경로 (None이면 임시 파일)
            
        Returns:
            생성된 프리즈 프레임 비디오 경로
        """
        if output_path is None:
            output_path = f"/tmp/freeze_{int(time.time() * 1000)}.mp4"
        
        # 1. 프레임 추출
        temp_frame = f"/tmp/frame_{int(time.time() * 1000)}.png"
        extract_cmd = [
            'ffmpeg', '-y',
            '-ss', str(frame_time),
            '-i', video_path,
            '-frames:v', '1',
            '-vf', 'scale=in_range=full:out_range=full',
            temp_frame
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Frame extraction failed: {result.stderr}")
            raise Exception(f"Frame extraction failed: {result.stderr}")
        
        # 2. 표준 무음 생성
        silence_wav = TemplateStandards.create_silence_wav(duration)
        
        try:
            # 3. 프레임과 무음 결합
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', temp_frame,
                '-i', silence_wav,
                '-t', str(duration),
                '-vf', f'scale={TemplateStandards.STANDARD_VIDEO_WIDTH}:{TemplateStandards.STANDARD_VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={TemplateStandards.STANDARD_VIDEO_WIDTH}:{TemplateStandards.STANDARD_VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
                '-preset', TemplateStandards.STANDARD_VIDEO_PRESET,
                '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
                '-pix_fmt', TemplateStandards.STANDARD_PIX_FMT,
                '-c:a', 'aac',
                '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
                '-shortest',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Freeze frame creation failed: {result.stderr}")
                raise Exception(f"Freeze frame creation failed: {result.stderr}")
            
            logger.debug(f"Created freeze frame: {output_path}")
            return output_path
            
        finally:
            # 임시 파일 정리
            for temp_file in [temp_frame, silence_wav]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
    
    @staticmethod
    def create_black_gap(duration: float, output_path: Optional[str] = None) -> str:
        """
        표준 검은 화면 갭 생성
        
        Args:
            duration: 갭 길이 (초)
            output_path: 출력 경로 (None이면 임시 파일)
            
        Returns:
            생성된 갭 비디오 경로
        """
        if output_path is None:
            output_path = f"/tmp/gap_{int(time.time() * 1000)}.mp4"
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s={TemplateStandards.STANDARD_VIDEO_WIDTH}x{TemplateStandards.STANDARD_VIDEO_HEIGHT}:d={duration}',
            '-f', 'lavfi',
            '-i', f'anullsrc=channel_layout={TemplateStandards.SILENCE_CHANNEL_LAYOUT}:sample_rate={TemplateStandards.SILENCE_SAMPLE_RATE}',
            '-t', str(duration),
            '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
            '-preset', 'veryfast',
            '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
            '-pix_fmt', TemplateStandards.STANDARD_PIX_FMT,
            '-c:a', 'aac',
            '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Black gap creation failed: {result.stderr}")
            raise Exception(f"Black gap creation failed: {result.stderr}")
        
        logger.debug(f"Created black gap: {output_path} ({duration}s)")
        return output_path
    
    @staticmethod
    def merge_clips(clips: List[str], output_path: str, mode: str = 'reencode') -> bool:
        """
        표준 방식으로 클립 병합
        
        Args:
            clips: 병합할 클립 경로들
            output_path: 출력 경로
            mode: 'copy' 또는 'reencode' (기본값: reencode)
            
        Returns:
            성공 여부
        """
        if not clips:
            logger.error("No clips to merge")
            return False
        
        # concat 파일 생성
        concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        try:
            for clip in clips:
                if os.path.exists(clip):
                    escaped_path = clip.replace('\\', '/').replace("'", "'\\''")
                    concat_file.write(f"file '{escaped_path}'\n")
            concat_file.close()
            
            if mode == 'copy':
                # 단순 복사 (빠르지만 호환성 문제 가능)
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file.name,
                    '-c', 'copy',
                    output_path
                ]
            else:
                # 재인코딩 (느리지만 안전)
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file.name,
                    '-c:v', TemplateStandards.STANDARD_VIDEO_CODEC,
                    '-preset', TemplateStandards.STANDARD_VIDEO_PRESET,
                    '-crf', str(TemplateStandards.STANDARD_VIDEO_CRF),
                    '-pix_fmt', TemplateStandards.STANDARD_PIX_FMT,
                    '-c:a', 'aac',
                    '-ar', str(TemplateStandards.OUTPUT_SAMPLE_RATE),
                    '-ac', str(TemplateStandards.OUTPUT_CHANNELS),
                    '-b:a', TemplateStandards.OUTPUT_AUDIO_BITRATE,
                    '-movflags', '+faststart',
                    output_path
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Merge failed: {result.stderr}")
                return False
            
            logger.info(f"Successfully merged {len(clips)} clips to {output_path}")
            return True
            
        finally:
            if os.path.exists(concat_file.name):
                os.remove(concat_file.name)
    
    @staticmethod
    def get_video_info(video_path: str) -> Dict:
        """
        비디오 정보 추출
        
        Args:
            video_path: 비디오 경로
            
        Returns:
            비디오 정보 딕셔너리
        """
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate,codec_name,pix_fmt',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if data.get('streams'):
                return data['streams'][0]
        
        return {}
    
    @staticmethod
    def get_audio_info(video_path: str) -> Dict:
        """
        오디오 정보 추출
        
        Args:
            video_path: 비디오 경로
            
        Returns:
            오디오 정보 딕셔너리
        """
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name,sample_rate,channels,channel_layout',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if data.get('streams'):
                return data['streams'][0]
        
        return {}


# 간편 사용을 위한 별칭
TS = TemplateStandards