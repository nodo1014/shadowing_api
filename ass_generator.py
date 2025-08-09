from typing import List, Dict, Tuple, Optional
import os
import re


class ASSGenerator:
    def __init__(self):
        # Default style settings based on README.md specifications
        self.styles = {
            "english": {
                "font_name": "Open Sans",
                "font_size": 32,  # 36 → 32로 조정
                "bold": True,
                "primary_color": "&HFFFFFF&",  # White
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 1,  # Standard outline
                "shadow": 0,  # No shadow for clean look
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 60  # 그대로 유지
            },
            "korean": {
                "font_name": "Noto Sans KR ExtraBold",
                "font_size": 32,  # 28 → 32로 조정
                "bold": False,
                "primary_color": "&H00FFFF&",  # Yellow (BGR: 00FFFF)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 1,  # Standard outline
                "shadow": 0,  # No shadow for clean look
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 60  # 20 → 60으로 조정
            },
            "note": {
                "font_name": "Noto Sans KR ExtraBold",
                "font_size": 24,  # As requested
                "bold": False,  # ExtraBold font already
                "primary_color": "&HFFFFFF&",  # White (BGR: FFFFFF)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 1,  # Standard outline
                "shadow": 0,  # No shadow for clean look
                "alignment": 7,  # Top left (7 = top left)
                "margin_l": 30,
                "margin_r": 30,
                "margin_v": 30
            },
            "no_subtitle_notice": {
                "font_name": "Noto Sans KR ExtraBold",
                "font_size": 40,
                "bold": False,
                "primary_color": "&H00FFFF&",  # Yellow (BGR: 00FFFF)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 1,  # Standard outline
                "shadow": 0,
                "alignment": 7,  # Top left
                "margin_l": 20,
                "margin_r": 20,
                "margin_v": 20
            },
            "shorts_title": {
                "font_name": "Tmon Monsori",  # 티몬 몬소리체 (설치 필요)
                "font_size": 42,  # 적절한 크기로 조정
                "bold": False,
                "primary_color": "&H00D7FF&",  # 밝은 주황색 (BGR: FFD700 골드에 가까운 주황)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 3,  # 두꺼운 아웃라인으로 가독성 확보
                "shadow": 4,  # 그림자로 입체감
                "alignment": 8,  # Top center (화면 상단 중앙)
                "margin_l": 5,  # 좌우 마진 최소화
                "margin_r": 5,
                "margin_v": 5  # 상단에서 5px만 떨어진 위치
            },
            # Shorts 전용 자막 스타일
            "shorts_english": {
                "font_name": "Open Sans",
                "font_size": 28,  # 36 → 28로 축소
                "bold": True,
                "primary_color": "&HFFFFFF&",  # White
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",
                "back_color": "&H00000000",
                "outline": 1,
                "shadow": 0,
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 40  # 하단 여백 줄임
            },
            "shorts_korean": {
                "font_name": "Noto Sans KR ExtraBold",
                "font_size": 22,  # 28 → 22로 축소
                "bold": False,
                "primary_color": "&H00FFFF&",  # Yellow
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",
                "back_color": "&H00000000",
                "outline": 1,
                "shadow": 0,
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 15  # 하단 여백 줄임
            },
            "shorts_note": {
                "font_name": "Noto Sans KR ExtraBold",
                "font_size": 20,  # 24 → 20으로 축소
                "bold": False,
                "primary_color": "&HFFFFFF&",  # White
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",
                "back_color": "&H00000000",
                "outline": 1,
                "shadow": 0,
                "alignment": 7,  # Top left
                "margin_l": 20,
                "margin_r": 20,
                "margin_v": 20
            }
        }
        
        # No resolution setting for better scaling across different video resolutions
        self.width = 0
        self.height = 0
        
    def generate_ass(self, subtitles: List[Dict], output_path: str, video_width: int = None, video_height: int = None, time_offset: float = 0.0, clip_duration: float = None, is_shorts: bool = False):
        """Generate ASS subtitle file from subtitle data"""
        # Keep resolution at 0 for better scaling regardless of video dimensions
        # This allows the subtitle renderer to scale fonts appropriately
        # time_offset: subtract this value from all subtitle times (for clipped videos)
        # clip_duration: if specified, show subtitles for the entire clip duration
        # is_shorts: if True, use shorts-specific styles
        
        # Auto-detect shorts from output path
        if not is_shorts and 'shorts' in output_path.lower():
            is_shorts = True
            print(f"[ASS DEBUG] Auto-detected shorts from path: {output_path}")
        
        # Apply time offset to subtitles
        adjusted_subtitles = []
        for sub in subtitles:
            adjusted_sub = sub.copy()
            
            if clip_duration is not None:
                # For the last subtitle or if there's only one subtitle,
                # extend it to the entire clip duration (including gap)
                if sub == subtitles[-1] or len(subtitles) == 1:
                    adjusted_sub['start_time'] = max(0, sub['start_time'] - time_offset)
                    adjusted_sub['end_time'] = clip_duration
                else:
                    # Keep original timing for other subtitles
                    adjusted_sub['start_time'] = max(0, sub['start_time'] - time_offset)
                    adjusted_sub['end_time'] = max(0, sub['end_time'] - time_offset)
            else:
                # Use original timing with offset
                adjusted_sub['start_time'] = max(0, sub['start_time'] - time_offset)
                adjusted_sub['end_time'] = max(0, sub['end_time'] - time_offset)
            
            # Only include subtitles that are within the video timeframe
            if adjusted_sub['end_time'] > 0:
                adjusted_subtitles.append(adjusted_sub)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(self._generate_header())
            
            # Write styles
            f.write(self._generate_styles(is_shorts=is_shorts))
            
            # Write events
            f.write(self._generate_events(adjusted_subtitles, is_shorts=is_shorts))
            
    def _generate_header(self) -> str:
        """Generate ASS file header without resolution settings for better scaling"""
        header = """[Script Info]
Title: Shadowing Subtitles
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0
Timer: 100.0000
Video Aspect Ratio: 0
Video Zoom: 0
Video Position: 0
WrapStyle: 0
ScaledBorderAndShadow: no

"""
        return header
    
    def _generate_styles(self, is_shorts: bool = False) -> str:
        """Generate styles section"""
        # Select appropriate styles based on is_shorts
        if is_shorts:
            english_style = self.styles["shorts_english"]
            korean_style = self.styles["shorts_korean"]
            note_style = self.styles["shorts_note"]
        else:
            english_style = self.styles["english"]
            korean_style = self.styles["korean"]
            note_style = self.styles["note"]
            
        print(f"[ASS DEBUG] Using {'shorts' if is_shorts else 'regular'} styles")
        print(f"[ASS DEBUG] Font settings - English: {english_style['font_name']}, Bold: {english_style['bold']}")
        print(f"[ASS DEBUG] Font settings - Korean: {korean_style['font_name']}, Bold: {korean_style['bold']}")
        styles = "[V4+ Styles]\n"
        styles += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        styles += "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        styles += "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        
        # English style
        styles += "Style: English,{},{},{},{},{},{},{},0,0,0,85,100,0,0,1,{},{},{},{},{},{},1\n".format(
            english_style["font_name"], english_style["font_size"], english_style["primary_color"], english_style["secondary_color"],
            english_style["outline_color"], english_style["back_color"], 1 if english_style["bold"] else 0,
            english_style["outline"], english_style["shadow"], english_style["alignment"],
            english_style["margin_l"], english_style["margin_r"], english_style["margin_v"]
        )
        
        # Korean style
        styles += "Style: Korean,{},{},{},{},{},{},{},0,0,0,85,100,0,0,1,{},{},{},{},{},{},1\n".format(
            korean_style["font_name"], korean_style["font_size"], korean_style["primary_color"], korean_style["secondary_color"],
            korean_style["outline_color"], korean_style["back_color"], 1 if korean_style["bold"] else 0,
            korean_style["outline"], korean_style["shadow"], korean_style["alignment"],
            korean_style["margin_l"], korean_style["margin_r"], korean_style["margin_v"]
        )
        
        # Note style
        styles += "Style: Note,{},{},{},{},{},{},{},0,0,0,85,100,0,0,1,{},{},{},{},{},{},1\n".format(
            note_style["font_name"], note_style["font_size"], note_style["primary_color"], note_style["secondary_color"],
            note_style["outline_color"], note_style["back_color"], 1 if note_style["bold"] else 0,
            note_style["outline"], note_style["shadow"], note_style["alignment"],
            note_style["margin_l"], note_style["margin_r"], note_style["margin_v"]
        )
        
        # No subtitle notice style
        no_sub = self.styles["no_subtitle_notice"]
        styles += "Style: NoSubtitleNotice,{},{},{},{},{},{},{},0,0,0,85,100,0,0,1,{},{},{},{},{},{},1\n".format(
            no_sub["font_name"], no_sub["font_size"], no_sub["primary_color"], no_sub["secondary_color"],
            no_sub["outline_color"], no_sub["back_color"], 1 if no_sub["bold"] else 0,
            no_sub["outline"], no_sub["shadow"], no_sub["alignment"],
            no_sub["margin_l"], no_sub["margin_r"], no_sub["margin_v"]
        )
        
        # Shorts title style
        shorts = self.styles["shorts_title"]
        # ScaleX, ScaleY를 줄여서 좌우/상하 압축, Spacing을 음수로 설정해서 자간 축소
        styles += "Style: ShortsTitle,{},{},{},{},{},{},{},0,0,0,90,90,-3,0,1,{},{},{},{},{},{},1\n".format(
            shorts["font_name"], shorts["font_size"], shorts["primary_color"], shorts["secondary_color"],
            shorts["outline_color"], shorts["back_color"], 1 if shorts["bold"] else 0,
            shorts["outline"], shorts["shadow"], shorts["alignment"],
            shorts["margin_l"], shorts["margin_r"], shorts["margin_v"]
        )
        
        styles += "\n"
        return styles
    
    def _generate_events(self, subtitles: List[Dict], is_shorts: bool = False) -> str:
        """Generate events section"""
        events = "[Events]\n"
        events += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        for sub in subtitles:
            print(f"[ASS DEBUG] Subtitle data: {sub}")
            start_time = self._format_time(sub['start_time'])
            end_time = self._format_time(sub['end_time'])
            
            # English subtitle (if available)
            if 'eng' in sub and sub['eng']:
                # Check if this is for Type 2 and we have keywords to highlight
                if 'keywords' in sub and sub['keywords'] and 'english' in sub:
                    # Use the 'english' field which should have the full text
                    highlighted_text = self._highlight_keywords(sub['english'], sub['keywords'])
                    events += "Dialogue: 0,{},{},English,,0,0,0,,{}\n".format(
                        start_time, end_time, highlighted_text
                    )
                else:
                    events += "Dialogue: 0,{},{},English,,0,0,0,,{}\n".format(
                        start_time, end_time, sub.get('english', sub['eng'])
                    )
            
            # Korean subtitle (if available)
            if 'kor' in sub and sub['kor']:
                events += "Dialogue: 0,{},{},Korean,,0,0,0,,{}\n".format(
                    start_time, end_time, sub.get('korean', sub['kor'])
                )
            
            # Note (if available)
            if 'note' in sub and sub['note']:
                events += "Dialogue: 1,{},{},Note,,0,0,0,,{}\n".format(
                    start_time, end_time, sub['note']
                )
        
        return events
    
    def _format_time(self, seconds: float) -> str:
        """Convert seconds to ASS time format (h:mm:ss.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        
        return "{}:{:02d}:{:02d}.{:02d}".format(hours, minutes, secs, centisecs)
    
    def _highlight_keywords(self, text: str, keywords: List[str]) -> str:
        """
        Highlight keywords in text with orange color using ASS color codes.
        ASS color code for orange: {\c&H0080FF&}
        Reset to white: {\c&HFFFFFF&}
        """
        if not keywords:
            return text
            
        # Sort keywords by length (longest first) to avoid partial replacements
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        
        highlighted_text = text
        for keyword in sorted_keywords:
            # Case-insensitive replacement while preserving original case
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted_text = pattern.sub(
                lambda m: f'{{\\c&H0080FF&}}{m.group()}{{\\c&HFFFFFF&}}',
                highlighted_text
            )
        
        return highlighted_text
    
    def update_style(self, style_name: str, **kwargs):
        """Update style settings"""
        if style_name in self.styles:
            self.styles[style_name].update(kwargs)
    
    def generate_no_subtitle_notice(self, output_path: str, duration: float = 5.0):
        """Generate ASS file with '자막 없이 듣기' notice for no-subtitle clips"""
        notice_subtitle = {
            'start_time': 0.0,
            'end_time': duration,
            'text': '자막 없이 듣기'
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(self._generate_header())
            
            # Write styles
            f.write(self._generate_styles())
            
            # Write events
            events = "[Events]\n"
            events += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            
            start_time = self._format_time(notice_subtitle['start_time'])
            end_time = self._format_time(notice_subtitle['end_time'])
            
            # Add animation effects
            # \fad(fade_in_ms, fade_out_ms) - fade effect
            # \move(x1,y1,x2,y2,start_ms,end_ms) - movement effect
            # \t(start_ms,end_ms,\fscx120\fscy120) - scale animation
            
            # Option 1: Fade in/out with slight movement (current)
            # animated_text = "{\\fad(500,500)}" + notice_subtitle['text']
            
            # Option 2: Slide in from left with fade
            # animated_text = "{\\fad(300,300)\\move(-100,20,20,20,0,300)}" + notice_subtitle['text']
            
            # Option 3: Scale up with fade (bounce effect)
            animated_text = "{\\fad(400,400)\\t(0,400,\\fscx110\\fscy110)\\t(400,600,\\fscx100\\fscy100)}" + notice_subtitle['text']
            
            events += "Dialogue: 0,{},{},NoSubtitleNotice,,0,0,0,,{}\n".format(
                start_time, end_time, animated_text
            )
            
            f.write(events)
    
    def generate_shorts_title(self, output_path: str, title_text: str, duration: float = 5.0):
        """Generate ASS file with title for shorts videos"""
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(self._generate_header())
            
            # Write styles - 두 번째 줄용 스타일 추가
            styles = self._generate_styles()
            # 두 번째 줄용 스타일 추가 (흰색)
            shorts2 = self.styles["shorts_title"].copy()
            shorts2["primary_color"] = "&HFFFFFF&"  # White
            styles = styles.rstrip() + "\n"
            styles += "Style: ShortsTitle2,{},{},{},{},{},{},{},0,0,0,90,90,-3,0,1,{},{},{},{},{},{},1\n".format(
                shorts2["font_name"], shorts2["font_size"], shorts2["primary_color"], shorts2["secondary_color"],
                shorts2["outline_color"], shorts2["back_color"], 1 if shorts2["bold"] else 0,
                shorts2["outline"], shorts2["shadow"], shorts2["alignment"],
                shorts2["margin_l"], shorts2["margin_r"], shorts2["margin_v"]
            )
            styles += "\n"
            f.write(styles)
            
            # Write events
            events = "[Events]\n"
            events += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            
            start_time = self._format_time(0.0)
            end_time = self._format_time(duration)
            
            # Check if title has newline
            if "\\N" in title_text:
                lines = title_text.split("\\N")
                if len(lines) >= 2:
                    # 첫째줄: 노란색 (ShortsTitle)
                    # 둘째줄: 흰색 (ShortsTitle2)
                    animated_title = "{\\fad(500,300)\\t(0,500,\\fscx120\\fscy120)\\t(500,800,\\fscx100\\fscy100)}"
                    animated_title += lines[0] + "\\N{\\r\\rShortsTitle2}" + lines[1]
                    
                    events += "Dialogue: 1,{},{},ShortsTitle,,0,0,0,,{}\n".format(
                        start_time, end_time, animated_title
                    )
                else:
                    # 한 줄만 있을 경우
                    animated_title = "{\\fad(500,300)\\t(0,500,\\fscx120\\fscy120)\\t(500,800,\\fscx100\\fscy100)}" + title_text
                    events += "Dialogue: 1,{},{},ShortsTitle,,0,0,0,,{}\n".format(
                        start_time, end_time, animated_title
                    )
            else:
                # 한 줄만 있을 경우
                animated_title = "{\\fad(500,300)\\t(0,500,\\fscx120\\fscy120)\\t(500,800,\\fscx100\\fscy100)}" + title_text
                events += "Dialogue: 1,{},{},ShortsTitle,,0,0,0,,{}\n".format(
                    start_time, end_time, animated_title
                )
            
            f.write(events)


if __name__ == "__main__":
    # Test the ASS generator
    import json
    
    generator = ASSGenerator()
    
    # Load translated subtitles
    json_file = "/home/kang/dev/youtube_maker/shadowing_maker_cli/output/Emily.in.Paris.S01E01.1080p.WEB.H264-CAKES_translated.json"
    
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            subtitles = json.load(f)
        
        # Generate ASS file
        output_file = json_file.replace('_translated.json', '.ass')
        generator.generate_ass(subtitles, output_file)
        
        print(f"Generated ASS file: {output_file}")
        print(f"Total subtitles: {len(subtitles)}")