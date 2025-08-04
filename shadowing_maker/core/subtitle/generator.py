"""
Subtitle generator module
"""
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Generate various types of subtitles for shadowing videos"""
    
    def __init__(self):
        # Import ASS generator
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent.parent))
        from ass_generator import ASSGenerator
        self.ass_generator = ASSGenerator()
    
    def generate_full_subtitle(
        self,
        subtitle_data: Dict,
        output_path: str,
        with_keywords: bool = False,
        clip_duration: Optional[float] = None,
        gap_duration: float = 0.0
    ) -> bool:
        """
        Generate full subtitle with both English and Korean
        
        Args:
            subtitle_data: Subtitle data dictionary
            output_path: Output ASS file path
            with_keywords: Highlight keywords (for template_2)
            clip_duration: Total clip duration
            gap_duration: Gap between repeats
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare subtitle for ASS generation
            subtitle = subtitle_data.copy()
            
            # Ensure timing info exists
            if 'start_time' not in subtitle:
                subtitle['start_time'] = 0.0
            if 'end_time' not in subtitle:
                subtitle['end_time'] = clip_duration if clip_duration else 5.0
            
            # Add English and Korean text
            subtitle['english'] = subtitle.get('text_eng', '')
            subtitle['korean'] = subtitle.get('text_kor', '')
            
            # Highlight keywords if requested
            if with_keywords and subtitle.get('keywords'):
                english_text = subtitle['english']
                for keyword in subtitle['keywords']:
                    # Highlight keywords with color
                    english_text = english_text.replace(
                        keyword,
                        f"{{\\c&H00FFFF&}}{keyword}{{\\c&HFFFFFF&}}"
                    )
                subtitle['english'] = english_text
            
            # Generate ASS file
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass(
                [subtitle], output_path,
                clip_duration=total_duration
            )
            
            logger.info(f"Generated full subtitle: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating full subtitle: {e}", exc_info=True)
            return False
    
    def generate_blank_subtitle(
        self,
        subtitle_data: Dict,
        output_path: str,
        with_korean: bool = False,
        clip_duration: Optional[float] = None,
        gap_duration: float = 0.0
    ) -> bool:
        """
        Generate blank subtitle (with underscores for keywords)
        
        Args:
            subtitle_data: Subtitle data dictionary
            output_path: Output ASS file path
            with_korean: Include Korean translation
            clip_duration: Total clip duration
            gap_duration: Gap between repeats
            
        Returns:
            True if successful, False otherwise
        """
        try:
            subtitle = subtitle_data.copy()
            
            # Ensure timing info exists
            if 'start_time' not in subtitle:
                subtitle['start_time'] = 0.0
            if 'end_time' not in subtitle:
                subtitle['end_time'] = clip_duration if clip_duration else 5.0
            
            # Create blank English text
            english_text = subtitle.get('text_eng', '')
            if subtitle.get('keywords'):
                for keyword in subtitle['keywords']:
                    # Replace keywords with underscores
                    blank = '_' * len(keyword)
                    english_text = english_text.replace(keyword, blank)
            
            subtitle['english'] = english_text
            subtitle['eng'] = english_text
            
            # Add Korean if requested
            if with_korean:
                subtitle['korean'] = subtitle.get('text_kor', '')
                subtitle['kor'] = subtitle.get('text_kor', '')
            else:
                subtitle['korean'] = ''
                subtitle['kor'] = ''
            
            # Generate ASS file
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass(
                [subtitle], output_path,
                clip_duration=total_duration
            )
            
            logger.info(f"Generated blank subtitle (korean={with_korean}): {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating blank subtitle: {e}", exc_info=True)
            return False
    
    def generate_korean_only_subtitle(
        self,
        subtitle_data: Dict,
        output_path: str,
        clip_duration: Optional[float] = None,
        gap_duration: float = 0.0
    ) -> bool:
        """
        Generate Korean-only subtitle
        
        Args:
            subtitle_data: Subtitle data dictionary
            output_path: Output ASS file path
            clip_duration: Total clip duration
            gap_duration: Gap between repeats
            
        Returns:
            True if successful, False otherwise
        """
        try:
            subtitle = subtitle_data.copy()
            
            # Ensure timing info exists
            if 'start_time' not in subtitle:
                subtitle['start_time'] = 0.0
            if 'end_time' not in subtitle:
                subtitle['end_time'] = clip_duration if clip_duration else 5.0
            
            # Set only Korean text
            subtitle['english'] = ''
            subtitle['eng'] = ''
            subtitle['korean'] = subtitle.get('text_kor', '')
            subtitle['kor'] = subtitle.get('text_kor', '')
            
            # Add note if available
            if subtitle.get('note'):
                subtitle['korean'] += f"\\N({subtitle['note']})"
            
            # Generate ASS file
            total_duration = clip_duration + gap_duration if clip_duration else None
            self.ass_generator.generate_ass(
                [subtitle], output_path,
                clip_duration=total_duration
            )
            
            logger.info(f"Generated Korean-only subtitle: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating Korean subtitle: {e}", exc_info=True)
            return False
    
    def generate_custom_subtitle(
        self,
        subtitle_data: Dict,
        output_path: str,
        english_text: Optional[str] = None,
        korean_text: Optional[str] = None,
        clip_duration: Optional[float] = None
    ) -> bool:
        """
        Generate custom subtitle with specified text
        
        Args:
            subtitle_data: Base subtitle data
            output_path: Output ASS file path
            english_text: Custom English text (None to omit)
            korean_text: Custom Korean text (None to omit)
            clip_duration: Total clip duration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            subtitle = subtitle_data.copy()
            
            # Ensure timing info exists
            if 'start_time' not in subtitle:
                subtitle['start_time'] = 0.0
            if 'end_time' not in subtitle:
                subtitle['end_time'] = clip_duration if clip_duration else 5.0
            
            # Set custom text
            subtitle['english'] = english_text or ''
            subtitle['eng'] = english_text or ''
            subtitle['korean'] = korean_text or ''
            subtitle['kor'] = korean_text or ''
            
            # Generate ASS file
            self.ass_generator.generate_ass(
                [subtitle], output_path,
                clip_duration=clip_duration
            )
            
            logger.info(f"Generated custom subtitle: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating custom subtitle: {e}", exc_info=True)
            return False