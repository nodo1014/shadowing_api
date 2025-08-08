#!/usr/bin/env python3
"""단어 학습 비디오 생성"""
import json
import subprocess
from pathlib import Path
from ffmpeg_utils import FFmpegProcessor
from subtitle_generator import SubtitleGenerator

class WordVideoGenerator:
    def __init__(self, audio_info_file="output/audio_info.json"):
        self.audio_info_file = audio_info_file
        self.output_dir = Path("output/videos")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        with open(audio_info_file, 'r', encoding='utf-8') as f:
            self.audio_info = json.load(f)
        
        self.ffmpeg = FFmpegProcessor()
        self.subtitle_gen = SubtitleGenerator(template_type='word')
    
    def create_word_subtitle(self, data, sequences):
        """단어 학습용 자막 생성"""
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
        lines.append(self.subtitle_gen.create_dialogue(
            0, total_time,
            'word_meaning', data['korean'], fade=False
        ))
        
        # 영어와 발음 표시 시점 계산
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
        
        # 영어 단어와 발음 (동시에 표시)
        if english_start_time is not None:
            lines.append(self.subtitle_gen.create_dialogue(
                english_start_time, total_time,
                'english', data['english'], fade=False
            ))
            
            # 발음도 영어와 동시에 표시
            if data.get('pronunciation'):
                lines.append(self.subtitle_gen.create_dialogue(
                    english_start_time, total_time,
                    'pronunciation', f"[{data['pronunciation']}]", fade=False
                ))
        
        return lines
    
    def create_word_sequences(self, item_info):
        """단어 학습 시퀀스 생성"""
        sequences = []
        data = item_info['data']
        durations = item_info['durations']
        audio_files = item_info['audio_files']
        
        # 1. 한글 뜻만
        sequences.append({
            'type': 'korean_only',
            'audio': audio_files['korean'],
            'duration': durations['korean']
        })
        
        # 2. 영어 단어 3회 반복 (2초 간격)
        for i in range(3):
            sequences.append({
                'type': f'english_{i+1}',
                'audio': audio_files['english'],
                'duration': durations['english']
            })
        
        return sequences
    
    def generate_word_video(self, item_info):
        """단어 비디오 생성"""
        idx = item_info['index']
        data = item_info['data']
        word_dir = self.output_dir / f"word_{idx:03d}"
        word_dir.mkdir(exist_ok=True)
        
        # 시퀀스 생성
        sequences = self.create_word_sequences(item_info)
        
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
        subtitle_lines = self.create_word_subtitle(data, sequences)
        ass_file = str(word_dir / f"subtitle_{idx:03d}.ass")
        self.subtitle_gen.save_subtitle(ass_file, subtitle_lines)  # 해상도 설정 제거
        
        # 오디오 연결 (간격 포함)
        audio_with_gaps = []
        audio_with_gaps.append(audio_files[0])  # 한글
        for i in range(3):  # 영어 3회
            audio_with_gaps.append(audio_files[1])  # 같은 영어 파일 재사용
        
        combined_audio = str(word_dir / f"combined_audio_{idx:03d}.mp3")
        self.ffmpeg.concatenate_audio(audio_with_gaps, combined_audio, gap=2.0)
        
        # 검정 비디오 생성
        black_video = str(word_dir / f"black_video_{idx:03d}.mp4")
        self.ffmpeg.create_black_video(total_duration, black_video)
        
        # 최종 비디오 생성
        final_video = str(self.output_dir / f"word_{idx:03d}_final.mp4")
        self.ffmpeg.merge_video_audio_subtitle(black_video, combined_audio, ass_file, final_video)
        
        print(f"Created word video: {final_video}")
        return final_video
    
    def generate_all_videos(self):
        """모든 단어 비디오 생성"""
        video_files = []
        
        for item_info in self.audio_info:
            if item_info['data'].get('type') == 'word':
                video_file = self.generate_word_video(item_info)
                video_files.append(video_file)
        
        if len(video_files) > 1:
            final_output = str(self.output_dir / "complete_words.mp4")
            self.ffmpeg.concatenate_videos(video_files, final_output)
        
        print(f"\nAll word videos generated in: {self.output_dir}")
        return video_files

def main():
    import sys
    
    # 단어 샘플 CSV 생성
    if len(sys.argv) < 2:
        from generate_english_video import EnglishLearningVideo
        import asyncio
        
        csv_file = "sample_words.csv"
        if not Path(csv_file).exists():
            csv_content = """number,type,category,english,korean,pronunciation
001,word,기초단어,apple,사과,애플
002,word,기초단어,book,책,북
003,word,기초단어,water,물,워터"""
            
            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            print(f"Created sample CSV: {csv_file}")
        
        # TTS 생성
        generator = EnglishLearningVideo(csv_file)
        asyncio.run(generator.run())
    
    # 비디오 생성
    video_gen = WordVideoGenerator()
    video_gen.generate_all_videos()

if __name__ == "__main__":
    main()