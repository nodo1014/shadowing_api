#!/usr/bin/env python3
"""FFmpeg 유틸리티 함수들"""
import subprocess
from pathlib import Path

class FFmpegProcessor:
    def __init__(self, width=1920, height=1080, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        
    def create_black_video(self, duration, output_file):
        """검정 배경 비디오 생성"""
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s={self.width}x{self.height}:r={self.fps}:d={duration}',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error creating black video: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return output_file
    
    def merge_video_audio_subtitle(self, video_file, audio_file, subtitle_file, output_file):
        """비디오, 오디오, 자막 합치기"""
        cmd = [
            'ffmpeg', '-y',
            '-i', video_file,
            '-i', audio_file,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-vf', f"ass={subtitle_file}",
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error merging video/audio/subtitle: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return output_file
    
    def concatenate_audio(self, audio_files, output_file, gap=0.5):
        """여러 오디오 파일을 하나로 연결 (간격 포함)"""
        # 임시 무음 파일 생성
        silence_file = str(Path(output_file).parent / "silence.mp3")
        self.create_silence(gap, silence_file)
        
        # 파일 리스트 생성 (오디오 + 무음 교대로)
        list_file = output_file.replace('.mp3', '_list.txt')
        with open(list_file, 'w') as f:
            for i, audio in enumerate(audio_files):
                audio_path = Path(audio).absolute()
                f.write(f"file '{audio_path}'\n")
                if i < len(audio_files) - 1:
                    f.write(f"file '{Path(silence_file).absolute()}'\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-acodec', 'libmp3lame',
            '-ar', '44100',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 정리
        Path(list_file).unlink(missing_ok=True)
        Path(silence_file).unlink(missing_ok=True)
        
        if result.returncode != 0:
            print(f"Error concatenating audio: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return output_file
    
    def create_silence(self, duration, output_file):
        """무음 오디오 생성"""
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=mono',
            '-t', str(duration),
            '-acodec', 'libmp3lame',
            output_file
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_file
    
    def concatenate_videos(self, video_files, output_file):
        """여러 비디오를 하나로 연결"""
        list_file = str(Path(output_file).parent / "video_list.txt")
        with open(list_file, 'w') as f:
            for video in video_files:
                video_path = Path(video).absolute()
                f.write(f"file '{video_path}'\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        Path(list_file).unlink(missing_ok=True)
        
        if result.returncode != 0:
            print(f"Error concatenating videos: {result.stderr}")
            print("Individual videos created successfully, but concatenation failed.")
            return None
        
        print(f"Created complete video: {output_file}")
        return output_file
    
    def get_audio_duration(self, audio_file):
        """오디오 파일 길이 구하기"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    
    def check_ffmpeg(self):
        """FFmpeg 설치 확인"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("FFmpeg is installed")
                return True
        except FileNotFoundError:
            print("FFmpeg is not installed!")
            return False
        return False