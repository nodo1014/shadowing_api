import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import subprocess
import cv2
import time
from video_encoder import VideoEncoder

logger = logging.getLogger(__name__)

class TemplateVideoEncoder(VideoEncoder):
    """템플릿 기반 비디오 인코더"""
    
    def __init__(self):
        super().__init__()
        self.templates_dir = Path("templates")
        self.templates_file = self.templates_dir / "shadowing_patterns.json"
        self.templates_cache = {}
        self._current_template_name = None
        
    def load_templates(self) -> Dict:
        """템플릿 로드"""
        if not self.templates_file.exists():
            return {}
        
        try:
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            return {}
    
    def get_template(self, template_name: str) -> Optional[Dict]:
        """특정 템플릿 가져오기"""
        if template_name not in self.templates_cache:
            templates = self.load_templates()
            # JSON 구조에서 patterns 키 안에 템플릿들이 있음
            patterns = templates.get('patterns', {})
            self.templates_cache[template_name] = patterns.get(template_name)
        return self.templates_cache[template_name]
    
    def validate_template(self, template: Dict) -> bool:
        """템플릿 유효성 검증"""
        required_fields = ['patterns', 'segment_duration', 'subtitle_style']
        for field in required_fields:
            if field not in template:
                logger.error(f"Missing required field: {field}")
                return False
        return True
    
    def apply_template(self, video_path: str, output_path: str, 
                      template_name: str, segments: List[Dict]) -> bool:
        """템플릿 적용하여 비디오 생성"""
        try:
            self._current_template_name = template_name
            logger.info(f"=== TemplateVideoEncoder.apply_template ===")
            logger.info(f"Template: {template_name}")
            logger.info(f"Video path: {video_path}")
            logger.info(f"Output path: {output_path}")
            
            template = self.get_template(template_name)
            if not template:
                logger.error(f"Template {template_name} not found!")
                return False
                
            logger.info(f"Template loaded: {json.dumps(template, indent=2)}")
            logger.info(f"Segments count: {len(segments)}")
            if segments:
                logger.info(f"First segment: {json.dumps(segments[0], indent=2)}")
            
            # 북마크된 세그먼트 확인
            bookmarked_count = sum(1 for seg in segments if seg.get('is_bookmarked', False))
            logger.info(f"Bookmarked segments: {bookmarked_count}")
            
            # template_91은 특별한 처리
            if template_name == 'template_91' and template.get('mode') == 'continuous_with_bookmarks':
                logger.info("Using continuous_with_bookmarks mode for template_91")
                return self._apply_continuous_template(video_path, output_path, template, segments)
            
            # 기존 템플릿 처리
            if not self.validate_template(template):
                return False
            
            # 세그먼트를 패턴에 따라 그룹화
            pattern_groups = self._group_segments_by_pattern(segments, template['patterns'])
            
            # 각 패턴별로 클립 생성
            clips = []
            for pattern_name, pattern_segments in pattern_groups.items():
                pattern_config = self._get_pattern_config(template, pattern_name)
                if not pattern_config:
                    continue
                
                pattern_clips = self._create_pattern_clips(
                    video_path, pattern_segments, pattern_config
                )
                clips.extend(pattern_clips)
            
            # 클립 병합
            if clips:
                return self._merge_clips(clips, output_path)
            
            return False
            
        except Exception as e:
            logger.error(f"Error applying template: {e}", exc_info=True)
            return False
    
    def _group_segments_by_pattern(self, segments: List[Dict], 
                                  patterns: List[str]) -> Dict[str, List[Dict]]:
        """세그먼트를 패턴별로 그룹화"""
        groups = {pattern: [] for pattern in patterns}
        pattern_index = 0
        
        for segment in segments:
            current_pattern = patterns[pattern_index % len(patterns)]
            groups[current_pattern].append(segment)
            pattern_index += 1
        
        return groups
    
    def _get_pattern_config(self, template: Dict, pattern_name: str) -> Optional[Dict]:
        """패턴 설정 가져오기"""
        patterns_config = template.get('patterns_config', {})
        return patterns_config.get(pattern_name)
    
    def _create_pattern_clips(self, video_path: str, segments: List[Dict], 
                            pattern_config: Dict) -> List[str]:
        """패턴별 클립 생성"""
        clips = []
        
        for i, segment in enumerate(segments):
            clip_path = f"/tmp/pattern_clip_{pattern_config['name']}_{i}.mp4"
            
            # 세그먼트 타입에 따른 처리
            if segment['type'] == 'video':
                self._create_video_clip(video_path, clip_path, segment, pattern_config)
            else:
                self._create_still_clip(video_path, clip_path, segment, pattern_config)
            
            if os.path.exists(clip_path):
                clips.append(clip_path)
        
        return clips
    
    def _create_video_clip(self, video_path: str, output_path: str, 
                          segment: Dict, pattern_config: Dict) -> bool:
        """비디오 클립 생성"""
        try:
            # 자막 파일 생성
            subtitle_file = None
            if segment.get('subtitle'):
                subtitle_file = self._create_subtitle_file(
                    segment['subtitle'], 
                    pattern_config.get('subtitle_style', {})
                )
            
            # 클립 인코딩
            success = self._encode_clip(
                video_path, 
                output_path,
                segment.get('start_time'),
                segment.get('duration'),
                subtitle_file
            )
            
            # 자막 파일 정리
            if subtitle_file and os.path.exists(subtitle_file):
                os.remove(subtitle_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating video clip: {e}")
            return False
    
    def _create_still_clip(self, video_path: str, output_path: str, 
                          segment: Dict, pattern_config: Dict) -> bool:
        """정지 화면 클립 생성"""
        try:
            still_type = pattern_config.get('still_type', 'freeze')
            duration = segment.get('duration', 3.0)
            
            if still_type == 'freeze':
                # 특정 프레임을 고정
                return self._create_freeze_frame_clip(
                    video_path, output_path, 
                    segment.get('frame_time', 0), 
                    duration
                )
            elif still_type == 'black':
                # 검은 화면
                return self._create_black_clip(output_path, duration)
            elif still_type == 'wrapup':
                # 정리 화면
                return self._create_wrapup_clip(
                    output_path, duration,
                    pattern_config.get('wrapup_text', 'Thank you!')
                )
            else:
                # 기본 정지 화면
                return self._create_default_still_clip(
                    video_path, output_path, duration
                )
                
        except Exception as e:
            logger.error(f"Error creating still clip: {e}")
            return False
    
    def _create_subtitle_file(self, subtitle_text: str, style_config: Dict) -> str:
        """자막 파일 생성
        
        .. deprecated:: 2025-08-25
           Use :class:`ass_generator.ASSGenerator` instead.
           이 메서드는 더 이상 사용되지 않습니다. 
           대신 ass_generator.ASSGenerator를 사용하세요.
        """
        subtitle_file = f"/tmp/subtitle_{int(time.time() * 1000)}.ass"
        
        # ASS 헤더 생성
        header = self._create_ass_header(style_config)
        
        # 자막 이벤트 생성
        events = self._create_ass_events(subtitle_text, style_config)
        
        # 파일 작성
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write("\n[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            f.write(events)
        
        return subtitle_file
    
    def _create_ass_header(self, style_config: Dict) -> str:
        """ASS 헤더 생성
        
        .. deprecated:: 2025-08-25
           Use :class:`ass_generator.ASSGenerator` instead.
           이 메서드는 더 이상 사용되지 않습니다. 
           대신 ass_generator.ASSGenerator를 사용하세요.
        """
        fontsize = style_config.get('fontsize', 45)
        fontname = style_config.get('fontname', 'TmonMonsori')
        color = style_config.get('color', '&H00FFFFFF')
        outline = style_config.get('outline', 2)
        shadow = style_config.get('shadow', 1)
        
        header = f"""[Script Info]
Title: Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},2,0,0,40,1
"""
        return header
    
    def _create_ass_events(self, text: str, style_config: Dict) -> str:
        """ASS 이벤트 생성
        
        .. deprecated:: 2025-08-25
           Use :class:`ass_generator.ASSGenerator` instead.
           이 메서드는 더 이상 사용되지 않습니다. 
           대신 ass_generator.ASSGenerator를 사용하세요.
        """
        # 간단히 전체 길이에 자막 표시
        start_time = "0:00:00.00"
        end_time = "0:10:00.00"  # 충분히 긴 시간
        
        event = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"
        return event
    
    def _create_freeze_frame_clip(self, video_path: str, output_path: str, 
                                 frame_time: float, duration: float) -> bool:
        """특정 프레임 고정 클립 생성 - 검은 배경 위에 프레임 올리기"""
        try:
            # 먼저 프레임 추출
            temp_frame = f"/tmp/freeze_frame_{int(time.time() * 1000)}.png"
            
            # 정확한 프레임 추출 (전체 화면 포함)
            extract_cmd = [
                'ffmpeg', '-y',
                '-ss', str(frame_time),
                '-i', video_path,
                '-frames:v', '1',
                '-vf', 'scale=in_range=full:out_range=full',  # 전체 범위 유지
                temp_frame
            ]
            
            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Frame extraction error: {result.stderr}")
                return False
            
            # 무음 WAV 파일 생성 (template 1과 동일한 방식)
            silence_wav = f"/tmp/silence_{int(time.time() * 1000)}.wav"
            silence_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', str(duration),
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                silence_wav
            ]
            
            result = subprocess.run(silence_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Silence generation error: {result.stderr}")
                if os.path.exists(temp_frame):
                    os.remove(temp_frame)
                return False
            
            # 검은 배경 위에 프레임을 올려서 무음 비디오 생성
            # 이미지와 WAV 파일을 결합
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', temp_frame,  # 추출한 프레임
                '-i', silence_wav,  # 무음 WAV
                '-t', str(duration),
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 임시 파일 삭제
            if os.path.exists(temp_frame):
                os.remove(temp_frame)
            if os.path.exists(silence_wav):
                os.remove(silence_wav)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating freeze frame: {e}")
            return False
    
    def _create_black_clip(self, output_path: str, duration: float) -> bool:
        """검은 화면 클립 생성"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=black:s=1920x1080:d={duration}',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating black clip: {e}")
            return False
    
    def _create_wrapup_clip(self, output_path: str, duration: float, 
                           wrapup_text: str) -> bool:
        """정리 화면 클립 생성"""
        try:
            # 텍스트를 여러 줄로 나누기
            lines = wrapup_text.split('\\n')
            drawtext_filter = []
            
            # 각 줄에 대해 drawtext 필터 생성
            for i, line in enumerate(lines):
                y_position = f"(h-text_h)/2 + {i * 60}"  # 줄 간격 60픽셀
                filter_part = (f"drawtext=text='{line}':"
                             f"fontfile=/home/kang/.fonts/TmonMonsori.ttf:"
                             f"fontsize=45:fontcolor=white:"
                             f"x=(w-text_w)/2:y={y_position}")
                drawtext_filter.append(filter_part)
            
            # 필터 결합
            filter_complex = ','.join(drawtext_filter)
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=purple:s=1920x1080:d={duration}',
                '-vf', filter_complex,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            logger.info("Wrapup clip created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating wrapup clip: {e}", exc_info=True)
            return False
    
    def _create_default_still_clip(self, video_path: str, output_path: str, 
                                  duration: float) -> bool:
        """기본 정지 화면 클립 생성"""
        try:
            # 첫 프레임 추출
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                # 비디오 읽기 실패시 검은 화면
                return self._create_black_clip(output_path, duration)
            
            # 프레임을 임시 이미지로 저장
            temp_image = f"/tmp/still_frame_{int(time.time() * 1000)}.jpg"
            cv2.imwrite(temp_image, frame)
            
            # 이미지를 비디오로 변환
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', temp_image,
                '-t', str(duration),
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 임시 이미지 삭제
            if os.path.exists(temp_image):
                os.remove(temp_image)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
            logger.info("Still frame clip created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating still frame clip: {e}", exc_info=True)
            return False
    
    def _encode_clip(self, input_path: str, output_path: str,
                    start_time: float = None, duration: float = None,
                    subtitle_file: str = None) -> bool:
        """비디오 클립 인코딩 - 쇼츠 템플릿일 경우 크롭 적용"""
        
        # 현재 템플릿이 쇼츠인지 확인
        current_template = getattr(self, '_current_template_name', '')
        is_shorts = '_shorts' in current_template
        
        # 쇼츠 여부를 부모 클래스에 전달
        if is_shorts:
            self._is_shorts_encoding = True
        
        if is_shorts:
            # 쇼츠용 크롭 적용
            return self._encode_clip_with_crop(input_path, output_path, 
                                             start_time, duration, 
                                             subtitle_file, 
                                             width=1080, height=1920)
        else:
            # 일반 인코딩
            return super()._encode_clip(input_path, output_path, 
                                      start_time, duration, 
                                      subtitle_file)
    
    def _encode_clip_with_crop(self, input_path: str, output_path: str,
                             start_time: float = None, duration: float = None,
                             subtitle_file: str = None, 
                             width: int = 1080, height: int = 1920) -> bool:
        """크롭을 적용한 클립 인코딩 (쇼츠용)"""
        
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # 비디오 필터 구성
        vf_filters = []
        
        # 크롭 및 스케일 필터
        vf_filters.append(f'crop=ih*{width}/{height}:ih,scale={width}:{height}')
        
        # 자막 필터 추가
        if subtitle_file:
            vf_filters.append(f"subtitles='{subtitle_file}'")
        
        # 필터 적용
        if vf_filters:
            cmd.extend(['-vf', ','.join(vf_filters)])
        
        # 인코딩 설정
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '16',
            '-c:a', 'copy',
            output_path
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False
        
        return True
    
    def _create_wrapup_clip(self, output_path: str, duration: float, wrapup_text: str):
        """정리 화면 클립 생성"""
        # 텍스트를 여러 줄로 나누기
        lines = wrapup_text.split('\\n')
        drawtext_filter = []
        
        # 각 줄에 대해 drawtext 필터 생성
        for i, line in enumerate(lines):
            y_position = f"(h-text_h)/2 + {i * 60}"  # 줄 간격 60픽셀
            filter_part = (f"drawtext=text='{line}':"
                         f"fontfile=/home/kang/.fonts/TmonMonsori.ttf:"
                         f"fontsize=45:fontcolor=white:"
                         f"x=(w-text_w)/2:y={y_position}")
            drawtext_filter.append(filter_part)
        
        # 필터 결합
        filter_complex = ','.join(drawtext_filter)
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=purple:s=1920x1080:d={duration}',
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '16',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True)
    
    def _create_default_still_clip(self, media_path: str, output_path: str, duration: float):
        """기본 정지화면 클립"""
        import subprocess
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s=1920x1080:d={duration}',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '16',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True)
    
    def _apply_vhs_effect(self, input_path: str, output_path: str) -> bool:
        """VHS 효과 적용"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', 'eq=brightness=0.05:saturation=1.3,'
                       'curves=preset=vintage,'
                       'noise=alls=20:allf=t,'
                       'chromashift=crh=10:cbh=-10',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                '-c:a', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"VHS effect error: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error applying VHS effect: {e}")
            return False
    
    def _apply_glitch_effect(self, input_path: str, output_path: str) -> bool:
        """글리치 효과 적용"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', 'lagfun=decay=0.99:planes=1,'
                       'rgbashift=rh=5:bv=5',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '16',
                '-c:a', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Glitch effect error: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error applying glitch effect: {e}")
            return False
    
    def _apply_continuous_template(self, video_path: str, output_path: str, 
                                  template: Dict, segments: List[Dict]) -> bool:
        """연속 재생 + 북마크 구간 템플릿 적용"""
        try:
            logger.info("=== _apply_continuous_template started ===")
            
            # 북마크된 세그먼트 찾기
            bookmarked_indices = [i for i, seg in enumerate(segments) if seg.get('is_bookmarked', False)]
            logger.info(f"Bookmarked indices: {bookmarked_indices}")
            
            if not bookmarked_indices:
                logger.warning("No bookmarked segments found. Processing all segments as continuous play.")
                # 북마크가 없으면 전체를 연속 재생으로 처리
                if segments:
                    start_time = segments[0]['start_time']
                    end_time = segments[-1]['end_time'] if 'end_time' in segments[-1] else segments[-1]['start_time'] + segments[-1].get('duration', 5)
                    duration = end_time - start_time
                    
                    # 전체 구간에 대한 자막 생성
                    subtitle_file = self._create_continuous_subtitle(segments, start_time)
                    
                    # 전체 비디오 인코딩
                    success = self._encode_clip(video_path, output_path, start_time, duration, subtitle_file)
                    
                    if subtitle_file and os.path.exists(subtitle_file):
                        os.remove(subtitle_file)
                    
                    return success
                else:
                    logger.error("No segments provided")
                    return False
            
            clips = []
            current_start = 0
            
            logger.info(f"Processing {len(bookmarked_indices)} bookmarked segments...")
            
            # 각 북마크를 순회하며 클립 생성
            for i, bookmark_idx in enumerate(bookmarked_indices):
                bookmark_segment = segments[bookmark_idx]
                
                # 북마크 전까지 연속 재생 (처음이 아니면)
                if bookmark_idx > current_start:
                    # 현재 위치부터 북마크 전까지 한 번에 인코딩
                    start_time = segments[current_start]['start_time']
                    end_time = bookmark_segment['start_time']
                    duration = end_time - start_time
                    
                    if duration > 0:
                        continuous_clip = f"/tmp/continuous_{i}_{int(time.time() * 1000)}.mp4"
                        
                        # 연속 구간 자막 파일 생성
                        subtitle_file = self._create_continuous_subtitle(
                            segments[current_start:bookmark_idx], 
                            start_time
                        )
                        
                        # 비디오 클립 생성 (영한자막)
                        if self._encode_clip(video_path, continuous_clip, 
                                           start_time, duration, subtitle_file):
                            clips.append(continuous_clip)
                        
                        if subtitle_file and os.path.exists(subtitle_file):
                            os.remove(subtitle_file)
                
                # 북마크 구간 - template_1 방식으로 반복
                logger.info(f"Creating template1 clips for bookmark {i+1}/{len(bookmarked_indices)}...")
                bookmark_clips = self._create_template1_clips(
                    video_path, bookmark_segment, i
                )
                clips.extend(bookmark_clips)
                logger.info(f"Created {len(bookmark_clips)} clips for bookmark segment")
                
                # 다음 시작 위치 업데이트
                current_start = bookmark_idx + 1
            
            # 마지막 북마크 이후 구간 처리
            if current_start < len(segments):
                start_time = segments[current_start]['start_time']
                # 마지막 세그먼트의 종료 시간 계산
                last_segment = segments[-1]
                end_time = last_segment['start_time'] + last_segment.get('duration', 2.0)
                duration = end_time - start_time
                
                if duration > 0:
                    final_clip = f"/tmp/continuous_final_{int(time.time() * 1000)}.mp4"
                    
                    # 마지막 구간 자막 파일 생성
                    subtitle_file = self._create_continuous_subtitle(
                        segments[current_start:], 
                        start_time
                    )
                    
                    if self._encode_clip(video_path, final_clip, 
                                       start_time, duration, subtitle_file):
                        clips.append(final_clip)
                    
                    if subtitle_file and os.path.exists(subtitle_file):
                        os.remove(subtitle_file)
            
            # 모든 클립 병합 - 프리즈프레임이 이미 포함되어 있으므로 gap 없이 병합
            if clips:
                logger.info(f"Merging {len(clips)} clips into final output...")
                success = self._merge_clips(clips, output_path)
                
                # 임시 파일 정리
                for clip in clips:
                    if os.path.exists(clip):
                        os.remove(clip)
                
                if success:
                    logger.info(f"✓ Successfully created template 91 video: {output_path}")
                else:
                    logger.error(f"✗ Failed to merge clips")
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Error applying continuous template: {e}", exc_info=True)
            return False
    
    def _create_continuous_subtitle(self, segments: List[Dict], offset_time: float) -> str:
        """연속 구간용 자막 파일 생성 (영한자막)"""
        subtitle_file = f"/tmp/continuous_subtitle_{int(time.time() * 1000)}.ass"
        
        # ASSGenerator 사용
        from ass_generator import ASSGenerator
        ass_gen = ASSGenerator()
        
        # 자막 데이터 변환
        subtitle_data = []
        for segment in segments:
            if segment.get('english_text') and segment.get('korean_text'):
                subtitle_data.append({
                    'start_time': segment['start_time'],
                    'end_time': segment['start_time'] + segment.get('duration', 2.0),
                    'eng': segment['english_text'],
                    'kor': segment['korean_text'],
                    'note': segment.get('note', '')
                })
        
        # ASS 파일 생성 (offset_time을 time_offset으로 전달)
        ass_gen.generate_ass(subtitle_data, subtitle_file, time_offset=offset_time)
        
        return subtitle_file
    
    def _seconds_to_ass_time(self, seconds: float) -> str:
        """초를 ASS 시간 형식으로 변환 (0:00:00.00)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def _merge_clips(self, clips: List[str], output_path: str) -> bool:
        """여러 클립을 하나로 병합"""
        try:
            if not clips:
                logger.error("No clips to merge")
                return False
            
            # FFmpeg concat 파일 생성
            concat_file = f"/tmp/concat_{int(time.time() * 1000)}.txt"
            with open(concat_file, 'w') as f:
                for clip in clips:
                    if os.path.exists(clip):
                        f.write(f"file '{clip}'\n")
            
            # FFmpeg로 병합 - 재인코딩하여 호환성 보장
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264',
                '-preset', 'medium', 
                '-crf', '16',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-ar', '48000',  # 표준 샘플레이트로 통일
                '-ac', '2',      # 스테레오로 통일
                '-b:a', '192k',
                '-movflags', '+faststart',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 임시 파일 정리
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            for clip in clips:
                if os.path.exists(clip):
                    os.remove(clip)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg merge error: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error merging clips: {e}")
            return False
    
    def _create_template1_clips(self, video_path: str, segment: Dict, 
                               bookmark_index: int) -> List[str]:
        """북마크 구간에 template_1 방식 적용 (5회 반복 + 프리즈프레임)"""
        clips = []
        modes = [
            ('no_subtitle', None),          # 무자막
            ('blank_subtitle', 'blank'),    # 빈 자막
            ('blank_korean', 'blank_korean'), # 빈칸+한글
            ('full_subtitle', 'full'),      # 영한자막
            ('no_subtitle', None)           # 무자막
        ]
        
        logger.info(f"Creating 5 variations for segment: {segment['start_time']:.2f}-{segment['end_time']:.2f}s")
        
        for i, (mode, subtitle_type) in enumerate(modes):
            # 일반 클립
            clip_path = f"/tmp/bookmark_{bookmark_index}_mode_{i}_{int(time.time() * 1000)}.mp4"
            
            # 자막 파일 생성
            subtitle_file = None
            if subtitle_type:
                subtitle_file = self._create_template1_subtitle(
                    segment, subtitle_type
                )
            
            # 클립 인코딩
            logger.info(f"  - Creating {mode} clip ({i+1}/5)...")
            if self._encode_clip(video_path, clip_path,
                               segment['start_time'],
                               segment.get('duration', 2.0),
                               subtitle_file):
                clips.append(clip_path)
                logger.info(f"    ✓ Created: {os.path.basename(clip_path)}")
                
                # 프리즈 프레임 생성 (각 클립 뒤에 0.5초)
                freeze_path = f"/tmp/bookmark_{bookmark_index}_freeze_{i}_{int(time.time() * 1000)}.mp4"
                freeze_time = segment['end_time'] - 0.1  # 끝 부분에서 프레임 추출
                
                if self._create_freeze_frame_clip(video_path, freeze_path, freeze_time, 0.5):
                    clips.append(freeze_path)
                    logger.info(f"    ✓ Created freeze frame: {os.path.basename(freeze_path)}")
                else:
                    logger.error(f"    ✗ Failed to create freeze frame")
            else:
                logger.error(f"    ✗ Failed to create {mode} clip")
            
            # 자막 파일 정리
            if subtitle_file and os.path.exists(subtitle_file):
                os.remove(subtitle_file)
        
        return clips
    
    def _create_template1_subtitle(self, segment: Dict, subtitle_type: str) -> str:
        """템플릿1 방식의 자막 생성"""
        subtitle_file = f"/tmp/template1_subtitle_{subtitle_type}_{int(time.time() * 1000)}.ass"
        
        # ASSGenerator 사용
        from ass_generator import ASSGenerator
        ass_gen = ASSGenerator()
        
        # 자막 데이터 준비
        subtitle_data = {
            'start_time': 0,
            'end_time': segment.get('duration', 2.0) + 0.5,  # 0.5초 추가 (gap_duration)
            'eng': segment['english_text'],
            'kor': segment['korean_text'],
            'note': segment.get('note', '')
        }
        
        # 자막 타입에 따른 처리
        if subtitle_type == 'blank':
            # 빈 자막 (영어를 _로 대체)
            subtitle_data['eng'] = ' '.join('_' * len(word) for word in segment['english_text'].split())
            subtitle_data['kor'] = ''  # 한글 제거
        elif subtitle_type == 'blank_korean':
            # 빈칸 + 한글
            subtitle_data['eng'] = ' '.join('_' * len(word) for word in segment['english_text'].split())
            # 한글은 그대로 유지
        elif subtitle_type == 'full':
            # 영한자막 - 그대로 사용
            pass
        else:
            return None
        
        # ASS 파일 생성
        ass_gen.generate_ass([subtitle_data], subtitle_file, 
                           clip_duration=segment.get('duration', 2.0) + 0.5)
        
        return subtitle_file