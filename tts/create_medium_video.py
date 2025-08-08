#!/usr/bin/env python3
"""
중급 문장 학습 비디오 생성기 (keywords 포함)
"""
import json
import re
from pathlib import Path
from subtitle_generator import SubtitleGenerator
from ffmpeg_utils import FFmpegProcessor

class MediumVideoGenerator:
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir) / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_gen = SubtitleGenerator(template_type="sentence_medium")
        self.ffmpeg = FFmpegProcessor()
    
    def create_blanked_text(self, text, keywords):
        """키워드를 '_'로 치환한 텍스트 생성"""
        blanked = text
        if keywords:
            keyword_list = keywords.split()
            for keyword in keyword_list:
                # 단어 경계를 고려한 치환
                pattern = r'\b' + re.escape(keyword) + r'\b'
                replacement = '_' * len(keyword)
                blanked = re.sub(pattern, replacement, blanked, flags=re.IGNORECASE)
        return blanked
    
    def create_highlighted_text(self, text, keywords):
        """키워드를 하이라이트한 텍스트 생성"""
        highlighted = text
        if keywords:
            keyword_list = keywords.split()
            for keyword in keyword_list:
                # ASS 태그로 노란색 하이라이트
                pattern = r'\b(' + re.escape(keyword) + r')\b'
                replacement = r'{\\c&H00FFFF&}\1{\\c&HFFFFFF&}'
                highlighted = re.sub(pattern, replacement, highlighted, flags=re.IGNORECASE)
        return highlighted
    
    def create_medium_subtitle(self, data, sequences):
        """중급 문장 학습용 자막 생성"""
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
        
        # 한글 뜻 (전체 시간 동안 고정)
        lines.append(self.subtitle_gen.create_dialogue(
            0, total_time,
            'word_meaning', data['korean'], fade=False
        ))
        
        # 영어 문장 처리 (시퀀스별로 다르게)
        current_time = 0.0
        
        for i, seq in enumerate(sequences):
            duration = seq['duration']
            start_time = current_time
            end_time = current_time + duration + 2.0
            
            if seq['type'] == 'korean':
                # 한글 오디오 재생 시간
                pass
            elif seq['type'] == 'english_1':
                # 첫 번째: 키워드를 '_'로 표시
                blanked_text = self.create_blanked_text(data['english'], data.get('keywords', ''))
                lines.append(self.subtitle_gen.create_dialogue(
                    start_time, end_time,
                    'english', blanked_text, fade=False
                ))
            elif seq['type'] in ['english_2', 'english_3']:
                # 두 번째, 세 번째: 키워드 하이라이트
                highlighted_text = self.create_highlighted_text(data['english'], data.get('keywords', ''))
                lines.append(self.subtitle_gen.create_dialogue(
                    start_time, end_time,
                    'english', highlighted_text, fade=False
                ))
            
            current_time = end_time
        
        # 노트 (영어 첫 등장부터)
        if data.get('note'):
            english_start = sum(s['duration'] for s in sequences if s['type'] == 'korean') + 2.0
            lines.append(self.subtitle_gen.create_dialogue(
                english_start, total_time,
                'note', data['note'], fade=False
            ))
        
        return lines
    
    def create_medium_sequences(self, item_info):
        """중급 문장 학습 시퀀스 생성"""
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
    
    def generate_medium_video(self, item_info):
        """중급 문장 비디오 생성"""
        idx = item_info['index']
        data = item_info['data']
        medium_dir = self.output_dir / f"medium_{idx:03d}"
        medium_dir.mkdir(exist_ok=True)
        
        # 시퀀스 생성
        sequences = self.create_medium_sequences(item_info)
        
        # 오디오 파일 리스트
        audio_files = []
        total_duration = 0
        
        for seq in sequences:
            if seq['audio']:
                audio_files.append(seq['audio'])
                total_duration += seq['duration']
        
        # 간격 추가 (각 오디오 사이 2초)
        total_duration += 2.0 * 3  # 한글-영어, 영어-영어 사이
        
        # ASS 자막 생성
        subtitle_lines = self.create_medium_subtitle(data, sequences)
        ass_file = str(medium_dir / f"subtitle_{idx:03d}.ass")
        self.subtitle_gen.save_subtitle(ass_file, subtitle_lines)
        
        # 오디오 연결 (간격 포함)
        audio_with_gaps = []
        audio_with_gaps.append(audio_files[0])  # 한글
        for i in range(3):  # 영어 3회
            audio_with_gaps.append(audio_files[1])
        
        combined_audio = str(medium_dir / f"combined_audio_{idx:03d}.mp3")
        self.ffmpeg.concatenate_audio(audio_with_gaps, combined_audio, gap=2.0)
        
        # 검정 비디오 생성
        black_video = str(medium_dir / f"black_video_{idx:03d}.mp4")
        self.ffmpeg.create_black_video(total_duration, black_video)
        
        # 최종 비디오 생성
        final_video = str(self.output_dir / f"medium_{idx:03d}_final.mp4")
        self.ffmpeg.merge_video_audio_subtitle(black_video, combined_audio, ass_file, final_video)
        
        print(f"Created medium video: {final_video}")
        return final_video
    
    def generate_all_videos(self):
        """모든 중급 문장 비디오 생성"""
        audio_info_file = Path("output/audio_info.json")
        if not audio_info_file.exists():
            print("Audio info file not found. Please generate TTS first.")
            return
        
        with open(audio_info_file, 'r', encoding='utf-8') as f:
            audio_info = json.load(f)
        
        video_files = []
        for item_info in audio_info:
            if item_info['data'].get('type') == 'sentence' and item_info['data'].get('keywords'):
                video_file = self.generate_medium_video(item_info)
                video_files.append(video_file)
        
        if len(video_files) > 1:
            final_output = str(self.output_dir / "complete_medium.mp4")
            self.ffmpeg.concatenate_videos(video_files, final_output)
        
        print(f"\nAll medium videos generated in: {self.output_dir}")
        return video_files

def main():
    import sys
    
    # CSV 파일 인자로 받기
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "sample_sentences_medium.csv"
    
    # TTS 생성이 필요한 경우
    if len(sys.argv) > 2 and sys.argv[2] == "--generate-tts":
        from generate_english_video import EnglishLearningVideo
        import asyncio
        
        if Path(csv_file).exists():
            generator = EnglishLearningVideo(csv_file)
            asyncio.run(generator.run())
    
    # 비디오 생성
    video_gen = MediumVideoGenerator()
    video_gen.generate_all_videos()

if __name__ == "__main__":
    main()