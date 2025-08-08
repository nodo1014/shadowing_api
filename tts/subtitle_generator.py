#!/usr/bin/env python3
"""ASS 자막 생성 모듈"""
import json
from pathlib import Path

class SubtitleGenerator:
    def __init__(self, template_type='word'):
        """
        template_type: 'word' or 'sentence'
        """
        self.template_type = template_type
        self.load_styles()
    
    def load_styles(self):
        """JSON 파일에서 스타일 로드"""
        styles_file = Path(__file__).parent / 'subtitle_styles.json'
        
        # 파일이 없으면 기본 스타일 사용
        if not styles_file.exists():
            self.styles = self.get_default_styles()
            return
        
        with open(styles_file, 'r', encoding='utf-8') as f:
            all_styles = json.load(f)
        
        # 템플릿 타입에 맞는 스타일 선택
        self.styles = all_styles.get(self.template_type, all_styles.get('word', {}))
    
    def get_default_styles(self):
        """기본 스타일 (JSON 파일이 없을 때)"""
        if self.template_type == 'sentence':
            return {
                'english': {
                    'fontname': 'DejaVu Sans',
                    'fontsize': 80,
                    'color': '&H00FFFFFF',
                    'alignment': 5,
                    'margin_v': 100,
                    'bold': -1
                },
                'korean': {
                    'fontname': 'Noto Sans CJK KR',
                    'fontsize': 52,
                    'color': '&H00FFFF00',
                    'alignment': 2,
                    'margin_v': 50,
                    'bold': -1
                },
                'note': {
                    'fontname': 'DejaVu Sans',
                    'fontsize': 40,
                    'color': '&H0000FF00',
                    'alignment': 8,
                    'margin_v': 50,
                    'bold': 0
                }
            }
        else:  # word
            return {
                'english': {
                    'fontname': 'Noto Sans',
                    'fontsize': 100,
                    'color': '&H00FFFFFF',
                    'alignment': 5,
                    'margin_v': -20,
                    'bold': -1
                },
                'pronunciation': {
                    'fontname': 'DejaVu Sans',
                    'fontsize': 28,
                    'color': '&H00FFFF00',
                    'alignment': 5,
                    'margin_v': 60,
                    'bold': 0
                },
                'word_meaning': {
                    'fontname': 'Noto Sans CJK KR',
                    'fontsize': 48,
                    'color': '&H00FFFFFF',
                    'alignment': 5,
                    'margin_v': 110,
                    'bold': -1
                },
                'category': {
                    'fontname': 'Noto Sans CJK KR',
                    'fontsize': 24,
                    'color': '&H00000000',
                    'alignment': 7,
                    'margin_v': 30,
                    'bold': -1
                },
                'number': {
                    'fontname': 'DejaVu Sans',
                    'fontsize': 42,
                    'color': '&H00FFFF00',
                    'alignment': 8,
                    'margin_v': 30,
                    'bold': -1
                }
            }
        
    def get_ass_header(self, play_res_x=None, play_res_y=None):
        """ASS 헤더 템플릿 생성"""
        header = "[Script Info]\n"
        header += "Title: English Learning Video\n"
        header += "ScriptType: v4.00+\n"
        header += "WrapStyle: 0\n"  # 스마트 줄바꿈 (상단 줄이 더 김)
        
        # 해상도 설정 (옵션)
        if play_res_x and play_res_y:
            header += f"PlayResX: {play_res_x}\n"
            header += f"PlayResY: {play_res_y}\n"
        
        header += "\n[V4+ Styles]\n"
        header += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        
        # 스타일 정의
        for style_name, style in self.styles.items():
            header += self.create_style_line(style_name, style)
        
        header += "\n[Events]\n"
        header += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        return header
    
    def create_style_line(self, name, style):
        """스타일 라인 생성"""
        bold = style.get('bold', 0)
        
        # 카테고리 스타일인 경우 배경 효과를 위해 큰 아웃라인 설정
        if name.lower() == 'category' and 'background' in style:
            outline_colour = style['background']  # 노란색 아웃라인
            outline = 15  # 큰 아웃라인으로 배경 효과
            shadow = 10  # 그림자 추가로 부드럽게
        else:
            outline_colour = "&H00000000"
            outline = 3  # 일반 아웃라인
            shadow = 0
        
        return (f"Style: {name.capitalize()},"
                f"{style['fontname']},"
                f"{style['fontsize']},"
                f"{style['color']},&H000000FF,{outline_colour},&H00000000,"
                f"{bold},0,0,0,100,100,0,0,1,{outline},{shadow},"
                f"{style['alignment']},10,10,{style['margin_v']},1\n")
    
    def seconds_to_ass_time(self, seconds):
        """초를 ASS 시간 형식으로 변환 (0:00:00.00)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def create_dialogue(self, start, end, style, text, fade=True):
        """대화 라인 생성"""
        start_str = self.seconds_to_ass_time(start)
        end_str = self.seconds_to_ass_time(end)
        
        effect = ""
        if fade:
            effect = "{\\fad(300,300)}"
        
        # 카테고리 스타일인 경우 텍스트 패딩만 추가
        if style.lower() == 'category':
            text = f"  {text}  "  # 텍스트 좌우 패딩
        
        return f"Dialogue: 0,{start_str},{end_str},{style.capitalize()},,0,0,0,,{effect}{text}\n"
    
    def create_word_subtitle(self, word_data, timings):
        """단어 학습용 자막 생성"""
        lines = []
        
        # 카테고리 (고정)
        if word_data.get('category'):
            lines.append(self.create_dialogue(
                0, timings['total_duration'],
                'note', word_data['category'], fade=False
            ))
        
        # 번호 (고정)
        if word_data.get('number'):
            lines.append(self.create_dialogue(
                0, timings['total_duration'],
                'note', f"No. {word_data['number']}", fade=False
            ))
        
        # 한글 뜻
        if timings.get('korean_start') is not None:
            lines.append(self.create_dialogue(
                timings['korean_start'],
                timings['korean_end'],
                'korean', word_data['korean']
            ))
        
        # 영어 단어
        if timings.get('english_start') is not None:
            lines.append(self.create_dialogue(
                timings['english_start'],
                timings['english_end'],
                'english', word_data['english']
            ))
            
            # 발음
            if word_data.get('pronunciation'):
                lines.append(self.create_dialogue(
                    timings['english_start'],
                    timings['english_end'],
                    'pronunciation', f"[{word_data['pronunciation']}]"
                ))
        
        return lines
    
    def create_sentence_subtitle(self, sentence_data, timings, template='advanced'):
        """문장 학습용 자막 생성"""
        lines = []
        
        if template == 'basic':
            # 초급 템플릿: 한글 -> 영어 반복
            lines.extend(self.create_basic_template(sentence_data, timings))
        else:
            # 고급 템플릿: 5단계 학습
            lines.extend(self.create_advanced_template(sentence_data, timings))
        
        return lines
    
    def create_basic_template(self, data, timings):
        """초급 템플릿 자막"""
        lines = []
        
        # 한글
        if 'korean' in timings:
            lines.append(self.create_dialogue(
                timings['korean']['start'],
                timings['korean']['end'],
                'korean', data['korean']
            ))
        
        # 영어 (반복)
        if 'english' in timings:
            for repeat in timings['english']:
                lines.append(self.create_dialogue(
                    repeat['start'],
                    repeat['end'],
                    'english', data['english']
                ))
        
        return lines
    
    def create_advanced_template(self, data, timings):
        """고급 템플릿 자막 (5단계)"""
        lines = []
        
        # 카테고리 (전체 시간 동안 표시)
        if data.get('category'):
            lines.append(self.create_dialogue(
                0, timings.get('total_duration', 20),
                'note', data['category'], fade=False
            ))
        
        # 1. 한글만
        if 'korean_only' in timings:
            t = timings['korean_only']
            lines.append(self.create_dialogue(
                t['start'], t['end'],
                'korean', data['korean']
            ))
        
        # 2. 무자막 (영어 음성만)
        # 자막 없음
        
        # 3. 빈칸 채우기
        if 'blank' in timings:
            t = timings['blank']
            if data.get('blank_text'):
                lines.append(self.create_dialogue(
                    t['start'], t['end'],
                    'english', data['blank_text']
                ))
            if data.get('note'):
                lines.append(self.create_dialogue(
                    t['start'], t['end'],
                    'note', data['note']
                ))
        
        # 4. 완전한 문장
        if 'full' in timings:
            t = timings['full']
            lines.append(self.create_dialogue(
                t['start'], t['end'],
                'english', data['english']
            ))
            lines.append(self.create_dialogue(
                t['start'], t['end'],
                'korean', data['korean']
            ))
            if data.get('note'):
                lines.append(self.create_dialogue(
                    t['start'], t['end'],
                    'note', data['note']
                ))
        
        # 5. 반복 (무자막)
        # 자막 없음
        
        return lines
    
    def save_subtitle(self, output_file, lines, play_res_x=None, play_res_y=None):
        """자막 파일 저장"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.get_ass_header(play_res_x, play_res_y))
            f.writelines(lines)
        return output_file