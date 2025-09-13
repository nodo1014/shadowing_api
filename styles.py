"""
자막 스타일 설정 중앙화
ASS 자막 파일의 스타일 정의를 관리
"""

# 자막 스타일 설정 (ASS 파일 포맷)
SUBTITLE_STYLES = {
    "english": {
        "font_name": "Noto Sans CJK KR",
        "font_size": 110,  # FHD 기준 적정 크기
        "bold": True,
        "primary_color": "&HFFFFFF&",  # White
        "secondary_color": "&H000000FF",
        "outline_color": "&H000000&",  # Black outline
        "back_color": "&H00000000",
        "outline": 3,  # 두꺼운 테두리
        "shadow": 0,  # No shadow for clean look
        "alignment": 2,  # Bottom center
        "margin_l": 50,
        "margin_r": 50,
        "margin_v": 420  # FHD 기준 하단 여백 (420px 위로 - 50px 더 위로 이동)
    },
    "korean": {
        "font_name": "Noto Sans CJK KR",
        "font_size": 90,  # FHD 기준 적정 크기 80->110
        "bold": True,
        "primary_color": "&H00D7FF&",  # Gold (BGR: 00D7FF = FFD700 in RGB)
        "secondary_color": "&H000000FF",
        "outline_color": "&H000000&",  # Black outline
        "back_color": "&H00000000",
        "outline": 3,  # 두꺼운 테두리
        "shadow": 0,  # No shadow for clean look
        "alignment": 2,  # Bottom center
        "margin_l": 50,
        "margin_r": 50,
        "margin_v": 170  # FHD 기준 하단 여백 (170px 위로, 영어와 200px 간격)
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
        "alignment": 5,  # Center (5 = center)
        "margin_l": 80,  # FHD 기준 좌측 여백
        "margin_r": 80,
        "margin_v": 50  # FHD 기준 하단 여백
    },
    "label": {
        "font_name": "Noto Sans CJK KR",
        "font_size": 110,
        "bold": True,
        "primary_color": "&HFFFFFF&",  # White
        "secondary_color": "&H000000FF",
        "outline_color": "&H000000&",  # Black outline
        "back_color": "&H00000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 9,  # Top right
        "margin_l": 80,
        "margin_r": 80,
        "margin_v": 80
    }
}

# YouTube Shorts용 조정된 스타일
# 9:16 비율 (1080x1920) 모바일 화면 최적화
# YouTube Shorts UI 요소 고려:
#   - 하단: 좋아요, 댓글, 공유, 음악 정보 등 (약 300px)
#   - 상단: 팔로우 버튼, 설명 텍스트 (약 100px)
#   - 중앙 1080x1080 정사각형 영역이 주요 콘텐츠 영역
SHORTS_ADJUSTMENTS = {
    "default": {
        "english": {
            "font_size": 60,  # 모바일 가독성을 위한 크기 (기존 100에서 축소)
            "margin_v": 450  # 영어가 위 (하단에서 450px 위)
        },
        "korean": {
            "font_size": 50,  # 영어보다 약간 작게 (기존 90에서 축소)
            "margin_v": 300  # 한글이 아래 (하단에서 350px 위)
        },
        "note": {
            "font_size": 40,  # 모바일용 축소 (기존 70에서)
            "margin_v": 120  # 상단 여백 증가 (상단 UI 피하기)
        },
        "label": {
            "font_size": 70,  # 모바일용 축소 (110 -> 70)
            "margin_v": 120  # 상단 여백 증가
        }
    },
    "template_3_shorts": {
        "english": {
            "font_size": 45,  # 더 작은 폰트 크기
            "margin_v": 310  # 한글 위 (하단에서 310px 위)
        },
        "korean": {
            "font_size": 40,  # 더 작은 폰트 크기
            "margin_v": 250  # YouTube UI 피해서 (하단에서 250px 위)
        },
        "note": {
            "font_size": 35,
            "margin_v": 120
        },
        "label": {
            "font_size": 40,
            "margin_v": 120
        }
    }
}

def get_ass_style_format():
    """ASS 파일의 Style 포맷 정의 반환"""
    return ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")

def format_ass_style(name: str, style: dict) -> str:
    """스타일 딕셔너리를 ASS 스타일 라인으로 변환"""
    # Get spacing value, default to 0 if not specified
    spacing = style.get("spacing", 0)
    return "Style: {},{},""{},{},{},{},{},{},0,0,0,100,100,{},0,1,{},{},{},{},{},{},1".format(
        name.capitalize(),
        style["font_name"],
        style["font_size"],
        style["primary_color"],
        style["secondary_color"],
        style["outline_color"],
        style["back_color"],
        1 if style["bold"] else 0,
        spacing,  # Character spacing (horizontal spacing between characters)
        style["outline"],
        style["shadow"],
        style["alignment"],
        style["margin_l"],
        style["margin_r"],
        style["margin_v"]
    )

def get_ass_styles_section(is_shorts: bool = False, template_name: str = None) -> str:
    """완전한 ASS Styles 섹션 반환"""
    styles = ["[V4+ Styles]", get_ass_style_format()]
    
    # 각 스타일에 대해 처리
    for style_name, style_data in SUBTITLE_STYLES.items():
        if style_name == "label":
            # Label 스타일은 그대로 사용
            styles.append(format_ass_style("Label", style_data))
        else:
            # Shorts 조정 적용
            if is_shorts:
                adjusted_style = style_data.copy()
                # 템플릿별 설정이 있으면 우선 적용, 없으면 default 사용
                if template_name and template_name in SHORTS_ADJUSTMENTS:
                    if style_name in SHORTS_ADJUSTMENTS[template_name]:
                        adjusted_style.update(SHORTS_ADJUSTMENTS[template_name][style_name])
                elif style_name in SHORTS_ADJUSTMENTS.get("default", {}):
                    adjusted_style.update(SHORTS_ADJUSTMENTS["default"][style_name])
                styles.append(format_ass_style(style_name, adjusted_style))
            else:
                styles.append(format_ass_style(style_name, style_data))
    
    return "\n".join(styles) + "\n"

# ASS 색상 코드 변환 도우미
def rgb_to_ass_color(r: int, g: int, b: int) -> str:
    """RGB 값을 ASS 색상 코드로 변환 (BGR 순서)"""
    return "&H{:02X}{:02X}{:02X}&".format(b, g, r)

# 자주 사용하는 색상 정의
ASS_COLORS = {
    "white": "&HFFFFFF&",
    "black": "&H000000&",
    "gold": "&H00D7FF&",  # RGB: FFD700
    "orange": "&H0080FF&",  # RGB: FF8000
    "red": "&H0000FF&",  # RGB: FF0000
    "blue": "&HFF0000&",  # RGB: 0000FF
    "green": "&H00FF00&",  # RGB: 00FF00
}