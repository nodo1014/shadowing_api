#!/usr/bin/env python3
"""
문장 학습 비디오 생성기
"""
import json
from pathlib import Path
from subtitle_generator import SubtitleGenerator
from ffmpeg_utils import FFmpegProcessor

class SentenceVideoGenerator:
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir) / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_gen = SubtitleGenerator(template_type="sentence_basic")
        self.ffmpeg = FFmpegProcessor()
    
    def calculate_font_scale(self, text, base_font_size=40, is_korean=False):
        """문장 길이에 따른 폰트 스케일 계산"""
        # 화면 너비와 마진 고려
        screen_width = 1920
        margin = 0.9  # 10% 마진
        effective_width = screen_width * margin
        
        # 한글과 영어의 문자 폭 차이
        char_width = base_font_size * (1.0 if is_korean else 0.6)
        chars_per_line = effective_width / char_width
        
        # 필요한 줄 수 계산
        lines_needed = len(text) / chars_per_line
        
        # 목표 줄 수 (한글 1줄, 영어 2줄)
        target_lines = 1 if is_korean else 2
        
        if lines_needed > target_lines:
            scale = int((target_lines * 100) / lines_needed)
            return max(scale, 70)  # 최소 70%
        
        return 100
    
    def create_sentence_subtitle(self, data, sequences):
        """문장 학습용 자막 생성"""
        lines = []
        total_time = sum(s['duration'] for s in sequences) + len(sequences) * 2.0
        
        # 카테고리 (전체 시간 동안 고정)
        if data.get('category'):
            lines.append(self.subtitle_gen.create_dialogue(
                0, total_time,
                'category', data['category'], fade=False
            ))
        
        # 번호 (전체 시간 동안 고정)
        if data.get('number'):
            lines.append(self.subtitle_gen.create_dialogue(
                0, total_time,
                'number', data['number'], fade=False
            ))
        
        # 한글 뜻 (전체 시간 동안 고정 - 항상 같은 위치)
        korean_text = data['korean']
        korean_scale = self.calculate_font_scale(korean_text, base_font_size=38, is_korean=True)
        
        if korean_scale < 100:
            korean_text = f"{{\\fscx{korean_scale}\\fscy{korean_scale}}}{korean_text}"
            
        lines.append(self.subtitle_gen.create_dialogue(
            0, total_time,
            'word_meaning', korean_text, fade=False
        ))
        
        # 영어와 노트 표시 시점 계산
        current_time = 0.0
        english_start_time = None
        
        for i, seq in enumerate(sequences):
            duration = seq['duration']
            start_time = current_time
            
            if seq['type'] == 'korean':
                # 한글 오디오 재생 시간
                pass
            elif seq['type'] == 'english_1':
                # 첫 번째 영어 오디오 시작 시점
                english_start_time = start_time
            
            current_time += duration + 2.0  # 2초 간격
        
        # 영어 문장과 노트 (동시에 표시)
        if english_start_time is not None:
            english_text = data['english']
            english_scale = self.calculate_font_scale(english_text, base_font_size=40, is_korean=False)
            
            if english_scale < 100:
                english_text = f"{{\\fscx{english_scale}\\fscy{english_scale}}}{english_text}"
            
            lines.append(self.subtitle_gen.create_dialogue(
                english_start_time, total_time,
                'english', english_text, fade=False
            ))
            
            # 노트도 영어와 동시에 표시
            if data.get('note'):
                lines.append(self.subtitle_gen.create_dialogue(
                    english_start_time, total_time,
                    'note', data['note'], fade=False
                ))
        
        return lines
    
    def create_sentence_sequences(self, item_info):
        """문장 학습 시퀀스 생성"""
        sequences = []
        data = item_info['data']
        durations = item_info['durations']
        audio_files = item_info['audio_files']
        
        # 1. 한글 (한글 뜻만)
        sequences.append({
            'type': 'korean',
            'audio': audio_files['korean'],
            'duration': durations['korean']
        })
        
        # 2-4. 영어 3회 반복
        for i in range(3):
            sequences.append({
                'type': f'english_{i+1}',
                'audio': audio_files['english'],
                'duration': durations['english']
            })
        
        return sequences
    
    def generate_sentence_video(self, item_info):
        """문장 비디오 생성"""
        idx = item_info['index']
        data = item_info['data']
        sentence_dir = self.output_dir / f"sentence_{idx:03d}"
        sentence_dir.mkdir(exist_ok=True)
        
        # 시퀀스 생성
        sequences = self.create_sentence_sequences(item_info)
        
        # 오디오 파일 리스트
        audio_files = []
        total_duration = 0
        
        for seq in sequences:
            if seq['audio']:
                audio_files.append(seq['audio'])
                total_duration += seq['duration']
        
        # 간격 추가 (각 오디오 사이 2초)
        total_duration += 2.0 * 3  # 한글-영어, 영어-영어 사이 (2초 x 3번)
        
        # ASS 자막 생성
        subtitle_lines = self.create_sentence_subtitle(data, sequences)
        ass_file = str(sentence_dir / f"subtitle_{idx:03d}.ass")
        self.subtitle_gen.save_subtitle(ass_file, subtitle_lines)
        
        # 오디오 연결 (간격 포함)
        audio_with_gaps = []
        audio_with_gaps.append(audio_files[0])  # 한글
        for i in range(3):  # 영어 3회
            audio_with_gaps.append(audio_files[1])  # 같은 영어 파일 재사용
        
        combined_audio = str(sentence_dir / f"combined_audio_{idx:03d}.mp3")
        self.ffmpeg.concatenate_audio(audio_with_gaps, combined_audio, gap=2.0)
        
        # 검정 비디오 생성
        black_video = str(sentence_dir / f"black_video_{idx:03d}.mp4")
        self.ffmpeg.create_black_video(total_duration, black_video)
        
        # 최종 비디오 생성
        final_video = str(self.output_dir / f"sentence_{idx:03d}_final.mp4")
        self.ffmpeg.merge_video_audio_subtitle(black_video, combined_audio, ass_file, final_video)
        
        print(f"Created sentence video: {final_video}")
        return final_video
    
    def generate_all_videos(self):
        """모든 문장 비디오 생성"""
        audio_info_file = Path("output/audio_info.json")
        if not audio_info_file.exists():
            print("Audio info file not found. Please generate TTS first.")
            return
        
        with open(audio_info_file, 'r', encoding='utf-8') as f:
            audio_info = json.load(f)
        
        video_files = []
        for item_info in audio_info:
            if item_info['data'].get('type') == 'sentence':
                video_file = self.generate_sentence_video(item_info)
                video_files.append(video_file)
        
        if len(video_files) > 1:
            final_output = str(self.output_dir / "complete_sentences.mp4")
            self.ffmpeg.concatenate_videos(video_files, final_output)
        
        print(f"\nAll sentence videos generated in: {self.output_dir}")
        return video_files

def main():
    import sys
    
    # CSV 파일 인자로 받기
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "sample_sentences_basic.csv"
    
    # TTS 생성이 필요한 경우
    if len(sys.argv) > 2 and sys.argv[2] == "--generate-tts":
        from generate_english_video import EnglishLearningVideo
        import asyncio
        
        if Path(csv_file).exists():
            # TTS 생성
            generator = EnglishLearningVideo(csv_file)
            asyncio.run(generator.run())
    
    # 비디오 생성
    video_gen = SentenceVideoGenerator()
    video_gen.generate_all_videos()

if __name__ == "__main__":
    main()