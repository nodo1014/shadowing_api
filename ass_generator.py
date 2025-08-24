from typing import List, Dict, Tuple, Optional
import os
import re


class ASSGenerator:
    def __init__(self):
        # Default style settings based on README.md specifications
        self.styles = {
            "english": {
                "font_name": "Noto Sans CJK KR",
                "font_size": 100,  # FHD 기준 적정 크기
                "bold": True,
                "primary_color": "&HFFFFFF&",  # White
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 3,  # 두꺼운 테두리
                "shadow": 0,  # No shadow for clean look
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 120  # FHD 기준 하단 여백
            },
            "korean": {
                "font_name": "Noto Sans CJK KR",
                "font_size": 90,  # FHD 기준 적정 크기
                "bold": True,
                "primary_color": "&H00D7FF&",  # Gold (BGR: 00D7FF = FFD700 in RGB)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 3,  # 두꺼운 테두리
                "shadow": 0,  # No shadow for clean look
                "alignment": 2,  # Bottom center
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 50  # FHD 기준 하단 여백
            },
            "note": {
                "font_name": "Noto Sans CJK KR",
                "font_size": 70,  # FHD 기준 적정 크기
                "bold": True,  # Bold for maximum thickness
                "primary_color": "&HFFFFFF&",  # White (BGR: FFFFFF)
                "secondary_color": "&H000000FF",
                "outline_color": "&H000000&",  # Black outline
                "back_color": "&H00000000",
                "outline": 3,  # 두꺼운 테두리
                "shadow": 0,  # No shadow for clean look
                "alignment": 7,  # Top left (7 = top left)
                "margin_l": 80,  # FHD 기준 좌측 여백
                "margin_r": 80,
                "margin_v": 80  # FHD 기준 상단 여백
            }
        }
        
        # No resolution setting for better scaling across different video resolutions
        self.width = 0
        self.height = 0
        
    def generate_ass(self, subtitles: List[Dict], output_path: str, video_width: int = None, video_height: int = None, time_offset: float = 0.0, clip_duration: float = None):
        """Generate ASS subtitle file from subtitle data"""
        # Keep resolution at 0 for better scaling regardless of video dimensions
        # This allows the subtitle renderer to scale fonts appropriately
        # time_offset: subtract this value from all subtitle times (for clipped videos)
        # clip_duration: if specified, show subtitles for the entire clip duration
        
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
            f.write(self._generate_styles())
            
            # Write events
            f.write(self._generate_events(adjusted_subtitles))
            
    def _generate_header(self) -> str:
        """Generate ASS file header with standard HD resolution"""
        header = """[Script Info]
Title: Shadowing Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Collisions: Normal
PlayDepth: 0
Timer: 100.0000
Video Aspect Ratio: 0
Video Zoom: 0
Video Position: 0
WrapStyle: 0
ScaledBorderAndShadow: yes

"""
        return header
    
    def _generate_styles(self) -> str:
        """Generate styles section"""
        styles = "[V4+ Styles]\n"
        styles += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        styles += "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        styles += "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        
        # English style
        eng = self.styles["english"]
        styles += "Style: English,{},{},{},{},{},{},{},0,0,0,100,100,0,0,1,{},{},{},{},{},{},1\n".format(
            eng["font_name"], eng["font_size"], eng["primary_color"], eng["secondary_color"],
            eng["outline_color"], eng["back_color"], 1 if eng["bold"] else 0,
            eng["outline"], eng["shadow"], eng["alignment"],
            eng["margin_l"], eng["margin_r"], eng["margin_v"]
        )
        
        # Korean style
        kor = self.styles["korean"]
        styles += "Style: Korean,{},{},{},{},{},{},{},0,0,0,100,100,0,0,1,{},{},{},{},{},{},1\n".format(
            kor["font_name"], kor["font_size"], kor["primary_color"], kor["secondary_color"],
            kor["outline_color"], kor["back_color"], 1 if kor["bold"] else 0,
            kor["outline"], kor["shadow"], kor["alignment"],
            kor["margin_l"], kor["margin_r"], kor["margin_v"]
        )
        
        # Note style
        note = self.styles["note"]
        styles += "Style: Note,{},{},{},{},{},{},{},0,0,0,100,100,0,0,1,{},{},{},{},{},{},1\n".format(
            note["font_name"], note["font_size"], note["primary_color"], note["secondary_color"],
            note["outline_color"], note["back_color"], 1 if note["bold"] else 0,
            note["outline"], note["shadow"], note["alignment"],
            note["margin_l"], note["margin_r"], note["margin_v"]
        )
        
        styles += "\n"
        return styles
    
    def _generate_events(self, subtitles: List[Dict]) -> str:
        """Generate events section"""
        events = "[Events]\n"
        events += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        for sub in subtitles:
            print(f"[ASS DEBUG] Subtitle data: {sub}")
            start_time = self._format_time(sub['start_time'])
            end_time = self._format_time(sub['end_time'])
            
            # Korean subtitle (if available) - Layer 0 (bottom)
            if 'kor' in sub and sub['kor']:
                events += "Dialogue: 0,{},{},Korean,,0,0,0,,{}\n".format(
                    start_time, end_time, sub.get('korean', sub['kor'])
                )
            
            # English subtitle (if available) - Layer 1 (above Korean)
            if 'eng' in sub and sub['eng']:
                # Check if this is for Type 2 and we have keywords to highlight
                if 'keywords' in sub and sub['keywords'] and 'english' in sub:
                    # Use the 'english' field which should have the full text
                    highlighted_text = self._highlight_keywords(sub['english'], sub['keywords'])
                    events += "Dialogue: 1,{},{},English,,0,0,0,,{}\n".format(
                        start_time, end_time, highlighted_text
                    )
                else:
                    events += "Dialogue: 1,{},{},English,,0,0,0,,{}\n".format(
                        start_time, end_time, sub.get('english', sub['eng'])
                    )
            
            # Note (if available) - Layer 2 (top)
            if 'note' in sub and sub['note']:
                events += "Dialogue: 2,{},{},Note,,0,0,0,,{}\n".format(
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