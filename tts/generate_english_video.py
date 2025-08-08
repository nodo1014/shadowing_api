#!/usr/bin/env python3
import csv
import os
import edge_tts
import asyncio
from pathlib import Path
import json
from mutagen.mp3 import MP3
import re

class EnglishLearningVideo:
    def __init__(self, csv_file, output_dir="output"):
        self.csv_file = csv_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.data = []
        self.audio_info = []
        
        self.tts_voices = {
            'korean': 'ko-KR-SunHiNeural',
            'english': 'en-US-JennyNeural'
        }
        
    def load_csv(self):
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data.append({
                    'number': row.get('number', '').strip(),
                    'type': row.get('type', 'sentence').strip(),
                    'category': row.get('category', '').strip(),
                    'english': row['english'].strip(),
                    'korean': row['korean'].strip(),
                    'keywords': row.get('keywords', '').strip(),
                    'note': row.get('note', '').strip(),
                    'pronunciation': row.get('pronunciation', '').strip()
                })
        print(f"Loaded {len(self.data)} entries from CSV")
        
    def create_blank_text(self, text, keywords):
        blank_text = text
        if keywords:
            for keyword in keywords.split(','):
                keyword = keyword.strip()
                pattern = r'\b' + re.escape(keyword) + r'\b'
                blank_text = re.sub(pattern, '_'*len(keyword), blank_text, flags=re.IGNORECASE)
        return blank_text
    
    async def generate_tts(self, text, voice, output_file):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        audio = MP3(output_file)
        duration = audio.info.length
        return duration
    
    async def generate_all_tts(self):
        for idx, item in enumerate(self.data):
            audio_dir = self.output_dir / f"sentence_{idx:03d}"
            audio_dir.mkdir(exist_ok=True)
            
            audio_files = {}
            durations = {}
            
            # 한글 TTS - 한 번만 생성
            kor_file = audio_dir / "korean.mp3"
            print(f"  Generating korean: {kor_file.name}")
            kor_duration = await self.generate_tts(item['korean'], self.tts_voices['korean'], str(kor_file))
            audio_files['korean'] = str(kor_file)
            durations['korean'] = kor_duration
            
            # 영어 TTS - 한 번만 생성 (모든 단계에서 재사용)
            eng_file = audio_dir / "english.mp3"
            print(f"  Generating english: {eng_file.name}")
            eng_duration = await self.generate_tts(item['english'], self.tts_voices['english'], str(eng_file))
            audio_files['english'] = str(eng_file)
            durations['english'] = eng_duration
            
            # 빈칸 처리된 텍스트 (TTS는 생성하지 않고 텍스트만 저장)
            blank_text = self.create_blank_text(item['english'], item['keywords'])
            
            self.audio_info.append({
                'index': idx,
                'data': item,
                'audio_files': audio_files,
                'durations': durations,
                'blank_text': blank_text
            })
            
            print(f"Completed sentence {idx+1}/{len(self.data)}")
        
        info_file = self.output_dir / "audio_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(self.audio_info, f, ensure_ascii=False, indent=2)
        print(f"\nAudio info saved to {info_file}")
    
    async def run(self):
        self.load_csv()
        await self.generate_all_tts()
        print("\nTTS generation complete!")
        print(f"Output directory: {self.output_dir}")

async def main():
    import sys
    
    if len(sys.argv) < 2:
        csv_content = """english,korean,keywords,note
I am a boy,나는 소년입니다,am,boy : 소년
I'm going to school,나는 학교에 가고 있어요,going,school : 학교
She likes apples,그녀는 사과를 좋아해요,likes,apple : 사과"""
        
        sample_csv = Path("sample.csv")
        with open(sample_csv, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        print(f"Created sample CSV file: {sample_csv}")
        csv_file = sample_csv
    else:
        csv_file = sys.argv[1]
    
    generator = EnglishLearningVideo(csv_file)
    await generator.run()

if __name__ == "__main__":
    asyncio.run(main())