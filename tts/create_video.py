#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
import os
from subtitle_generator import SubtitleGenerator

class VideoGenerator:
    def __init__(self, audio_info_file="output/audio_info.json"):
        self.audio_info_file = audio_info_file
        self.output_dir = Path("output/videos")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        with open(audio_info_file, 'r', encoding='utf-8') as f:
            self.audio_info = json.load(f)
        
        self.width = 1920
        self.height = 1080
        self.fps = 30
        self.subtitle_gen = SubtitleGenerator(template_type='sentence')
        
    def create_ass_subtitle_no_resolution(self, text_lines, durations, output_file):
        """ASS 자막 파일 생성 (해상도 설정 없음)"""
        ass_header = """[Script Info]
Title: English Learning Video
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,DejaVu Sans,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,10,10,100,1
Style: Korean,Noto Sans CJK KR,52,&H00FFFF00,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1
Style: Note,DejaVu Sans,40,&H0000FF00,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        lines = []
        current_time = 0.0
        
        for line_data in text_lines:
            start_time = current_time
            end_time = start_time + line_data['duration']
            
            start_str = self.seconds_to_ass_time(start_time)
            end_str = self.seconds_to_ass_time(end_time)
            
            if line_data.get('english'):
                lines.append(f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{{\\fad(300,300)}}{line_data['english']}")
            
            if line_data.get('korean'):
                lines.append(f"Dialogue: 0,{start_str},{end_str},Korean,,0,0,0,,{{\\fad(300,300)}}{line_data['korean']}")
            
            if line_data.get('note'):
                lines.append(f"Dialogue: 0,{start_str},{end_str},Note,,0,0,0,,{{\\fad(300,300)}}{line_data['note']}")
            
            current_time = end_time + 0.5  # 0.5초 간격
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ass_header)
            f.write('\n'.join(lines))
        
        return output_file
    
    def seconds_to_ass_time(self, seconds):
        """초를 ASS 시간 형식으로 변환 (0:00:00.00)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
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
        subprocess.run(cmd, check=True, capture_output=True)
        return output_file
    
    def merge_video_audio_subtitle(self, video_file, audio_file, subtitle_file, output_file):
        """비디오, 오디오, 자막 합치기"""
        cmd = [
            'ffmpeg', '-y',
            '-i', video_file,
            '-i', audio_file,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '128k',  # 오디오 비트레이트 설정
            '-ar', '44100',  # 오디오 샘플레이트 설정
            '-vf', f"ass={subtitle_file}",
            '-map', '0:v:0',  # 첫 번째 입력의 비디오 스트림
            '-map', '1:a:0',  # 두 번째 입력의 오디오 스트림
            '-shortest',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg merge error: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return output_file
    
    def create_learning_sequence(self, item_info):
        """5단계 학습 시퀀스 생성"""
        sequences = []
        data = item_info['data']
        durations = item_info['durations']
        audio_files = item_info['audio_files']
        blank_text = item_info.get('blank_text', '')
        
        # 1. 한글만
        sequences.append({
            'type': 'korean_only',
            'audio': audio_files['korean'],
            'duration': durations['korean'],
            'subtitle_lines': [{
                'korean': data['korean'],
                'duration': durations['korean']
            }]
        })
        
        # 2. 무자막 영어
        sequences.append({
            'type': 'english_nosub',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_lines': []
        })
        
        # 3. 빈칸 영어 + 노트
        if blank_text and blank_text != data['english']:
            sequences.append({
                'type': 'english_blank',
                'audio': audio_files['english'],
                'duration': durations['english'],
                'subtitle_lines': [{
                    'english': blank_text,
                    'note': data.get('note', ''),
                    'duration': durations['english']
                }]
            })
        
        # 4. 완전한 영어 + 한글 + 노트
        sequences.append({
            'type': 'english_full',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_lines': [{
                'english': data['english'],
                'korean': data['korean'],
                'note': data.get('note', ''),
                'duration': durations['english']
            }]
        })
        
        # 5. 무자막 영어 (반복)
        sequences.append({
            'type': 'english_final',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_lines': []
        })
        
        return sequences
    
    def create_blank_text(self, text, keywords):
        """키워드를 빈칸으로 치환"""
        import re
        blank_text = text
        if keywords:
            for keyword in keywords.split(','):
                keyword = keyword.strip()
                pattern = r'\b' + re.escape(keyword) + r'\b'
                blank_text = re.sub(pattern, '_'*len(keyword), blank_text, flags=re.IGNORECASE)
        return blank_text
    
    def concatenate_audio(self, audio_files, output_file):
        """여러 오디오 파일을 하나로 연결"""
        # 파일 리스트 생성
        list_file = output_file.replace('.mp3', '_list.txt')
        with open(list_file, 'w') as f:
            for i, audio in enumerate(audio_files):
                audio_path = Path(audio).absolute()
                f.write(f"file '{audio_path}'\n")
                if i < len(audio_files) - 1:
                    # 0.5초 정적 추가 (마지막 파일 제외)
                    f.write(f"duration 0.5\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-acodec', 'libmp3lame',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        os.remove(list_file)
        return output_file
    
    def generate_video_for_sentence(self, item_info):
        """한 문장에 대한 전체 비디오 생성"""
        idx = item_info['index']
        sentence_dir = self.output_dir / f"sentence_{idx:03d}"
        sentence_dir.mkdir(exist_ok=True)
        
        sequences = self.create_learning_sequence(item_info)
        
        # 전체 자막 데이터 수집
        all_subtitle_lines = []
        audio_files = []
        total_duration = 0
        
        for seq in sequences:
            audio_files.append(seq['audio'])
            total_duration += seq['duration'] + 0.5
            
            for line in seq['subtitle_lines']:
                line_copy = line.copy()
                line_copy['start'] = sum(d['duration'] + 0.5 for d in all_subtitle_lines)
                all_subtitle_lines.append(line_copy)
        
        # ASS 자막 생성 (해상도 설정 제거)
        ass_file = str(sentence_dir / f"subtitle_{idx:03d}.ass")
        self.create_ass_subtitle_no_resolution(all_subtitle_lines, total_duration, ass_file)
        
        # 오디오 연결
        combined_audio = str(sentence_dir / f"combined_audio_{idx:03d}.mp3")
        self.concatenate_audio(audio_files, combined_audio)
        
        # 검정 비디오 생성
        black_video = str(sentence_dir / f"black_video_{idx:03d}.mp4")
        self.create_black_video(total_duration, black_video)
        
        # 최종 비디오 생성
        final_video = str(self.output_dir / f"sentence_{idx:03d}_final.mp4")
        self.merge_video_audio_subtitle(black_video, combined_audio, ass_file, final_video)
        
        print(f"Created video: {final_video}")
        return final_video
    
    def generate_all_videos(self):
        """모든 문장에 대한 비디오 생성"""
        video_files = []
        
        for item_info in self.audio_info:
            video_file = self.generate_video_for_sentence(item_info)
            video_files.append(video_file)
        
        # 전체 비디오 연결
        if len(video_files) > 1:
            self.concatenate_videos(video_files)
        
        print(f"\nAll videos generated in: {self.output_dir}")
        return video_files
    
    def concatenate_videos(self, video_files):
        """여러 비디오를 하나로 연결"""
        list_file = str(self.output_dir / "video_list.txt")
        with open(list_file, 'w') as f:
            for video in video_files:
                video_path = Path(video).absolute()
                f.write(f"file '{video_path}'\n")
        
        final_output = str(self.output_dir / "complete_lesson.mp4")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            final_output
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            # 비디오 연결 실패해도 개별 비디오는 생성됨
            print("Individual videos created successfully, but concatenation failed.")
        else:
            os.remove(list_file)
            print(f"Created complete video: {final_output}")
        
        return final_output if result.returncode == 0 else None

def main():
    generator = VideoGenerator()
    generator.generate_all_videos()

if __name__ == "__main__":
    main()