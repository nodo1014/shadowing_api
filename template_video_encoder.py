"""
Template-based video encoder
템플릿 기반으로 shadowing 비디오를 생성하는 개선된 인코더
"""
import json
import os
import tempfile
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from video_encoder import VideoEncoder
from subtitle_generator import SubtitleGenerator
from subtitle_pipeline import SubtitlePipeline, SubtitleType
from img_tts_generator import ImgTTSGenerator

logger = logging.getLogger(__name__)


class TemplateVideoEncoder(VideoEncoder):
    """템플릿 기반 비디오 인코더"""
    
    def __init__(self):
        super().__init__()
        self.subtitle_generator = SubtitleGenerator()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """템플릿 파일 로드"""
        template_path = Path(__file__).parent / "templates" / "shadowing_patterns.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('patterns', {})
        return {}
    
    def create_from_template(self, template_name: str, media_path: str, 
                           subtitle_data: Dict, output_path: str,
                           start_time: float = None, end_time: float = None,
                           padding_before: float = 0.5, padding_after: float = 0.5,
                           save_individual_clips: bool = True) -> bool:
        """템플릿을 사용하여 shadowing 비디오 생성"""
        
        if template_name not in self.templates:
            logger.error(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        logger.info(f"Using template: {template['name']} - {template['description']}")
        
        # 현재 템플릿 이름 저장 (쇼츠 여부 확인용)
        self._current_template_name = template_name
        
        # 타이틀 정보 저장 (쇼츠용)
        self._title_line1 = subtitle_data.get('title_1', '')
        self._title_line2 = subtitle_data.get('title_2', '')
        self._title_line3 = subtitle_data.get('title_3', '')
        
        # Calculate padded times
        if start_time is not None and end_time is not None:
            padded_start = max(0, start_time - padding_before)
            padded_end = end_time + padding_after
            duration = padded_end - padded_start
        else:
            padded_start = None
            duration = None
        
        # Get gap duration from template
        gap_duration = template.get('gap_duration', 1.5)
        
        # Prepare subtitle files with gap duration
        subtitle_files = self._prepare_subtitle_files(subtitle_data, template_name, duration, gap_duration)
        
        # Create clips based on template
        temp_clips = []
        clip_base_dir = None
        
        if save_individual_clips:
            clip_base_dir = Path(output_path).parent / "individual_clips"
            clip_base_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            clip_number = Path(output_path).stem.split('_')[-1] if '_' in Path(output_path).stem else '0000'
            
            # 전체 클립 수 계산
            total_clips = sum(clip['count'] for clip in template['clips'])
            current_clip_index = 0
            
            for clip_config in template['clips']:
                for i in range(clip_config['count']):
                    current_clip_index += 1
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                    temp_clips.append(temp_file.name)
                    temp_file.close()
                    
                    # Get subtitle file for this clip
                    subtitle_file = subtitle_files.get(clip_config['subtitle_type'])
                    
                    # Store progress info for encoding
                    self._current_clip_index = current_clip_index
                    self._total_clips = total_clips
                    
                    # Check if this clip should use still frame mode
                    video_mode = clip_config.get('video_mode', 'normal')
                    
                    # Check for pre_silence
                    pre_silence = clip_config.get('pre_silence', 0.0)
                    post_silence = clip_config.get('post_silence', 0.0)
                    
                    # Create temporary clip without pre_silence first
                    temp_clip_no_silence = None
                    if pre_silence > 0:
                        temp_clip_no_silence = tempfile.NamedTemporaryFile(suffix='_no_silence.mp4', delete=False)
                        temp_clip_no_silence.close()
                        actual_output = temp_clip_no_silence.name
                    else:
                        actual_output = temp_clips[-1]
                    
                    # Encode the clip based on video mode
                    if video_mode == 'still_frame':
                        if not self._encode_still_frame_clip(media_path, actual_output,
                                                           padded_start, duration,
                                                           subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create still frame {clip_config['subtitle_mode']} clip")
                    elif video_mode in ['still_frame_tts', 'still_frame_original', 'still_frame_kor_tts'] and clip_config.get('use_img_tts_generator'):
                        # Use img_tts_generator for study clips
                        if not self._encode_study_clip(media_path, actual_output,
                                                      padded_start, duration,
                                                      subtitle_data, clip_config):
                            raise Exception(f"Failed to create study {clip_config['subtitle_mode']} clip")
                    elif video_mode == 'slow_motion':
                        # Slow motion video with speed adjustment
                        speed = clip_config.get('speed', 0.7)
                        if not self._encode_slow_motion_clip(media_path, actual_output,
                                                           padded_start, duration,
                                                           subtitle_file=subtitle_file,
                                                           speed=speed):
                            raise Exception(f"Failed to create slow motion {clip_config['subtitle_mode']} clip")
                    else:
                        if not self._encode_clip(media_path, actual_output,
                                               padded_start, duration,
                                               subtitle_file=subtitle_file):
                            raise Exception(f"Failed to create {clip_config['subtitle_mode']} clip")
                    
                    # Add pre_silence if needed
                    if pre_silence > 0 and temp_clip_no_silence:
                        # 쫼츠 여부 확인
                        is_shorts = '_shorts' in self._current_template_name if hasattr(self, '_current_template_name') else False
                        resolution = (1080, 1920) if is_shorts else (1920, 1080)
                        
                        # Create black video for pre_silence and concatenate
                        cmd = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi',
                            '-i', f'color=black:s={resolution[0]}x{resolution[1]}:d={pre_silence}',
                            '-f', 'lavfi', 
                            '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={pre_silence}',
                            '-i', temp_clip_no_silence.name,
                            '-filter_complex',
                            '[0:v][2:v]concat=n=2:v=1:a=0[outv];[1:a][2:a]concat=n=2:v=0:a=1[outa]',
                            '-map', '[outv]',
                            '-map', '[outa]',
                            '-c:v', 'libx264',
                            '-preset', 'medium',
                            '-crf', '22',
                            '-c:a', 'aac',
                            '-b:a', '192k',
                            '-movflags', '+faststart',
                            temp_clips[-1]
                        ]
                        
                        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
                        if returncode != 0:
                            logger.error(f"Failed to add pre_silence: {stderr}")
                            raise Exception(f"Failed to add pre_silence to {clip_config['subtitle_mode']} clip")
                        
                        # Clean up temporary file
                        os.unlink(temp_clip_no_silence.name)
                    
                    # Save individual clip if requested
                    if save_individual_clips and clip_base_dir:
                        folder_name = clip_config.get('folder_name', clip_config['subtitle_mode'])
                        self._save_individual_clip(temp_clips[-1], clip_base_dir,
                                                 folder_name, i + 1, clip_number)
                    
                    logger.info(f"Created {clip_config['subtitle_mode']} clip {i+1}/{clip_config['count']}")
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Concatenate clips with gaps
            gap_duration = template.get('gap_duration', 1.5)
            logger.info(f"Using gap_duration from template '{template_name}': {gap_duration} seconds")
            if not self._concatenate_clips(temp_clips, output_path, gap_duration):
                raise Exception("Failed to concatenate clips")
            
            logger.info(f"Successfully created shadowing video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating video from template: {e}", exc_info=True)
            return False
            
        finally:
            # Clean up
            for temp_clip in temp_clips:
                if os.path.exists(temp_clip):
                    os.unlink(temp_clip)
            
            # Clean up subtitle files
            for subtitle_file in subtitle_files.values():
                if subtitle_file and os.path.exists(subtitle_file):
                    os.unlink(subtitle_file)
    
    def _prepare_subtitle_files(self, subtitle_data: Dict, template_name: str, clip_duration: float = None, gap_duration: float = 0.0) -> Dict[str, str]:
        """템플릿에 필요한 자막 파일들을 준비 - 새로운 파이프라인 사용"""
        subtitle_files = {}
        
        # 템플릿에서 필요한 subtitle_type들을 추출
        template = self.templates.get(template_name)
        if not template:
            return subtitle_files
            
        needed_types = set()
        for clip in template['clips']:
            if clip['subtitle_type']:
                needed_types.add(clip['subtitle_type'])
        
        # Add timing information if not present
        if 'start_time' not in subtitle_data:
            subtitle_data['start_time'] = 0.0
        if 'end_time' not in subtitle_data:
            subtitle_data['end_time'] = clip_duration if clip_duration else 5.0
            
        # 효율적인 자막 파이프라인 사용
        # 쇼츠 템플릿인 경우 줄바꿈 설정 추가
        is_shorts = '_shorts' in template_name
        if is_shorts:
            subtitle_data['max_chars_per_line'] = 15  # 쇼츠용 짧은 줄
            subtitle_data['is_shorts'] = True
        pipeline = SubtitlePipeline(subtitle_data)
        
        # Map template subtitle types to pipeline types
        type_mapping = {
            'full': SubtitleType.FULL,
            'blank': SubtitleType.BLANK,
            'korean': SubtitleType.KOREAN_ONLY,
            'blank_korean': SubtitleType.BLANK_KOREAN,
        }
        
        # Gap duration을 포함한 총 클립 길이 계산
        total_clip_duration = clip_duration + gap_duration if clip_duration else None
        
        # 필요한 자막 파일들 생성 (파이프라인 사용)
        for subtitle_type in needed_types:
            if subtitle_type in type_mapping:
                variant_type = type_mapping[subtitle_type]
                
                # 임시 파일 생성
                temp_file = tempfile.NamedTemporaryFile(suffix=f'_{subtitle_type}.ass', delete=False)
                temp_file.close()
                
                # 파이프라인으로 자막 저장
                pipeline.save_variant_to_file(variant_type, temp_file.name, total_clip_duration)
                subtitle_files[subtitle_type] = temp_file.name
                
                logger.debug(f"Generated {subtitle_type} subtitle using pipeline")
        
        # 기존 방식으로 fallback (pipeline에서 지원하지 않는 타입)
        if len(subtitle_files) < len(needed_types):
            missing_types = needed_types - set(subtitle_files.keys())
            logger.warning(f"Pipeline doesn't support types: {missing_types}, using legacy generator")
            
            for subtitle_type in missing_types:
                # Legacy subtitle generation code here if needed
                pass
        
        return subtitle_files
    
    def _save_individual_clip(self, clip_path: str, base_dir: Path, 
                            clip_type: str, index: int, clip_number: str):
        """개별 클립 저장"""
        import shutil
        
        # subtitle_mode를 기반으로 디렉토리 이름 생성
        # 새로운 mode가 추가되어도 자동으로 처리됨
        sub_dir = base_dir / clip_type
        sub_dir.mkdir(exist_ok=True)
        
        dest_file = sub_dir / f"clip_{clip_number}_{index}.mp4"
        shutil.copy2(clip_path, str(dest_file))
        logger.debug(f"Saved: {dest_file.relative_to(base_dir)}")
    
    def _encode_still_frame_clip(self, input_path: str, output_path: str,
                                start_time: float = None, duration: float = None,
                                subtitle_file: str = None) -> bool:
        """정지화면 클립 생성 - 기존 방식 유지 (자막은 FFmpeg ass 필터 사용)"""
        import subprocess
        import os
        
        try:
            # 시작 시점의 프레임 추출
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
                img_path = img_file.name
            
            # 프레임 추출 (시작 시점에서 0.1초 후)
            extract_time = start_time + 0.1 if start_time else 0.1
            
            extract_cmd = [
                'ffmpeg', '-y',
                '-ss', str(extract_time),
                '-i', input_path,
                '-vframes', '1',
                '-q:v', '2',
                img_path
            ]
            
            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to extract frame: {result.stderr}")
                return False
            
            # 정지화면과 오디오 결합
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-framerate', '30',
                '-i', img_path
            ]
            
            # 오디오 추가
            if start_time is not None:
                cmd.extend(['-ss', str(start_time)])
            cmd.extend(['-i', input_path])
            
            if duration is not None:
                cmd.extend(['-t', str(duration)])
            
            # 비디오 설정 (FFmpeg 최적화 옵션 유지)
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '20',
                '-profile:v', 'high',
                '-level', '4.1',
                '-pix_fmt', 'yuv420p',
                '-tune', 'film',
                '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
                '-r', '30'
            ])
            
            # 오디오 설정
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '192k',
                '-af', 'aresample=async=1',
                '-map', '0:v',
                '-map', '1:a'
            ])
            
            # 비디오 필터 구성
            vf_filters = []
            
            # 자막 추가 (ASS 파일 사용 - 기존 스타일 시스템 유지)
            if subtitle_file and os.path.exists(subtitle_file):
                subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
                vf_filters.append(f"ass='{subtitle_path}'")
            
            # 템플릿에 타이틀 추가
            title_filter = self._get_title_filter()
            if title_filter:
                vf_filters.append(title_filter)
            
            if vf_filters:
                cmd.extend(['-vf', ','.join(vf_filters)])
            
            cmd.extend([
                '-shortest',
                '-movflags', '+faststart',
                output_path
            ])
            
            logger.debug(f"Creating still frame clip: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 임시 이미지 파일 삭제
            os.unlink(img_path)
            
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
            # 일반 인코딩 (타이틀 필터 적용을 위해 오버라이드)
            return self._encode_clip_with_title(input_path, output_path, 
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
        
        # 템플릿 이름에 따라 다른 크롭 방식 적용
        current_template = getattr(self, '_current_template_name', '')
        
        if 'template_1_shorts' in current_template:
            # 쇼츠 1: 원본 100% 정사각형 크롭
            video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        elif 'template_2_shorts' in current_template:
            # 쇼츠 2: 좌우 15%씩 크롭, 원본 높이 유지
            video_filter = f"crop='iw*0.7:ih:iw*0.15:0',scale='if(gt(iw,1080),1080,iw)':'if(gt(iw,1080),ih*1080/iw,ih)',pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        elif 'template_3_shorts' in current_template:
            # 쇼츠 3: 원본 크기 그대로 축소하여 전체 화면 보이기
            video_filter = f"scale='if(gt(iw/ih,{width}/{height}),{width},-1)':'if(gt(iw/ih,{width}/{height}),-1,{height})',pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        else:
            # 기본값: 원본 100% 정사각형 크롭
            video_filter = f"crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        
        if subtitle_file and os.path.exists(subtitle_file):
            subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
            video_filter += f",ass='{subtitle_path}'"
        
        # 템플릿에 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            video_filter += f",{title_filter}"
        
        cmd.extend(['-vf', video_filter])
        
        # 인코딩 설정 (일반 인코딩과 동일하게 통일)
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '22',
            '-profile:v', 'high',
            '-level', '4.1',
            '-pix_fmt', 'yuv420p',
            '-tune', 'film',
            '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            output_path
        ])
        
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _get_title_filter(self) -> str:
        """템플릿별 타이틀 필터 생성"""
        title1 = getattr(self, '_title_line1', '')
        title2 = getattr(self, '_title_line2', '')
        title3 = getattr(self, '_title_line3', '')
        
        if not title1 and not title2 and not title3:
            return ""
        
        filters = []
        
        # 폰트 파일 경로 설정 (여러 가능한 경로 시도)
        font_paths = [
            "/home/kang/.fonts/TmonMonsori.ttf",  # 실제 설치된 경로
            os.path.expanduser("~/.fonts/TmonMonsori.ttf"),  # 홈 디렉토리 확장
            "/usr/share/fonts/truetype/TmonMonsori.ttf",
            "/usr/local/share/fonts/TmonMonsori.ttf",
            "./fonts/TmonMonsori.ttf"
        ]
        
        font_file = None
        for path in font_paths:
            if os.path.exists(path):
                font_file = path
                break
        
        if not font_file:
            logger.warning("TmonMonsori font not found, using default font")
            font_file = "NanumGothic"  # 한글 지원되는 기본 폰트
        
        # 현재 템플릿 확인
        current_template = getattr(self, '_current_template_name', '')
        is_shorts = '_shorts' in current_template
        
        if is_shorts:
            # 쇼츠 템플릿: 중앙 정렬, 위아래 배치
            # 템플릿별로 다른 y 위치 설정
            if 'template_1_shorts' in current_template:
                base_y = 150  # 정사각형 크롭은 기본값
            elif 'template_2_shorts' in current_template:
                base_y = 250  # 좌우 크롭은 상하 여백이 더 큼
            elif 'template_3_shorts' in current_template:
                base_y = 350  # 전체 화면은 상하 여백이 가장 큼
            else:
                base_y = 150  # 기본값
            
            # 첫 번째 줄 (흰색, 120pt)
            if title1:
                # 이스케이프 처리
                text1 = title1.replace(":", "\\:").replace("'", "\\'")
                filters.append(
                    f"drawtext=text='{text1}':fontfile='{font_file}':fontsize=120:"
                    f"fontcolor=white:x=(w-text_w)/2:y={base_y}"
                )
            
            # 두 번째 줄 (골드색, 90pt)
            if title2:
                # 이스케이프 처리
                text2 = title2.replace(":", "\\:").replace("'", "\\'")
                # 첫 번째 줄이 있으면 그 아래 적절한 간격으로
                y_pos = base_y + 150 if title1 else base_y  # 120(font) + 30(gap) = 150
                filters.append(
                    f"drawtext=text='{text2}':fontfile='{font_file}':fontsize=90:"
                    f"fontcolor=#FFD700:x=(w-text_w)/2:y={y_pos}"
                )
            
            # 세 번째 줄 (흰색, 60pt, 왼쪽 정렬, 여러 줄 지원)
            if title3:
                # 이스케이프 처리 (\n은 유지)
                text3 = title3.replace(":", "\\:").replace("'", "\\'")
                # title2가 있으면 그 아래, 없으면 title1 아래
                if title2:
                    y_pos3 = y_pos + 120  # 90(font) + 30(gap)
                elif title1:
                    y_pos3 = base_y + 150  # 120(font) + 30(gap)
                else:
                    y_pos3 = base_y
                
                filters.append(
                    f"drawtext=text='{text3}':fontfile='{font_file}':fontsize=60:"
                    f"fontcolor=white:x=100:y={y_pos3}"  # 왼쪽 여백 100px
                )
        else:
            # 일반 템플릿: 좌우 배치, 모두 흰색
            # 첫 번째 줄 (왼쪽, 흰색)
            if title1:
                # 이스케이프 처리
                text1 = title1.replace(":", "\\:").replace("'", "\\'")
                filters.append(
                    f"drawtext=text='{text1}':fontfile='{font_file}':fontsize=40:"
                    f"fontcolor=white:x=50:y=50"
                )
            
            # 두 번째 줄 (오른쪽, 흰색)
            if title2:
                # 이스케이프 처리
                text2 = title2.replace(":", "\\:").replace("'", "\\'")
                filters.append(
                    f"drawtext=text='{text2}':fontfile='{font_file}':fontsize=40:"
                    f"fontcolor=white:x=w-text_w-50:y=50"
                )
        
        return ",".join(filters)
    
    def _encode_clip_with_title(self, input_path: str, output_path: str,
                               start_time: float = None, duration: float = None,
                               subtitle_file: str = None) -> bool:
        """일반 템플릿용 타이틀이 적용된 클립 인코딩"""
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # 비디오 필터 구성
        vf_filters = []
        
        # 자막 추가
        if subtitle_file and os.path.exists(subtitle_file):
            subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
            vf_filters.append(f"ass='{subtitle_path}'")
        
        # 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            vf_filters.append(title_filter)
        
        if vf_filters:
            cmd.extend(['-vf', ','.join(vf_filters)])
        
        # 인코딩 설정
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '22',
            '-profile:v', 'high',
            '-level', '4.1',
            '-pix_fmt', 'yuv420p',
            '-tune', 'film',
            '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            output_path
        ])
        
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
    
    def _encode_study_clip(self, input_path: str, output_path: str,
                          start_time: float = None, duration: float = None,
                          subtitle_data: Dict = None, clip_config: Dict = None) -> bool:
        """스터디 클립 생성 - img_tts_generator 사용"""
        try:
            # ImgTTSGenerator 초기화
            generator = ImgTTSGenerator()
            
            # 템플릿 타입 확인
            is_shorts = "shorts" in clip_config.get("subtitle_mode", "")
            is_preview = "preview" in clip_config.get("subtitle_mode", "")
            
            # 해상도 설정
            if is_shorts:
                resolution = (1080, 1920)
                # 쇼츠용 크롭 필터 (template_1_shorts 스타일 - 정사각형 크롭, 화면에 가득 차도록)
                crop_filter = "crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            else:
                resolution = (1920, 1080)
                crop_filter = None
            
            # 프레임 추출 시간 (시작 시간에서 0.1초 후)
            extract_time = start_time + 0.1 if start_time else 0.1
            
            # 텍스트 준비
            texts = []
            if subtitle_data:
                texts.append({
                    "text": subtitle_data.get("text_kor", ""),
                    "style": {}
                })
                texts.append({
                    "text": subtitle_data.get("text_eng", ""),
                    "style": {}
                })
            
            # 오디오 설정 (원본 오디오 또는 TTS)
            use_original_audio = clip_config.get('use_original_audio', False)
            use_korean_tts = clip_config.get('use_korean_tts', False)
            
            if use_original_audio:
                # 원본 오디오 사용
                audio_source = {
                    'type': 'extract',
                    'path': input_path,
                    'start': start_time,
                    'end': start_time + duration if duration else None
                }
                tts_config = None
            else:
                # TTS 사용
                if use_korean_tts:
                    # 한글 TTS
                    tts_text = subtitle_data.get("text_kor", "") if subtitle_data else ""
                    voice = "ko-KR-SunHiNeural"  # Edge TTS sunhee 음성
                    rate = "+0%"
                else:
                    # 영어 TTS
                    tts_text = subtitle_data.get("text_eng", "") if subtitle_data else ""
                    voice = "en-US-AriaNeural"  # Edge TTS Aria 음성
                    rate = "+0%" if is_preview else "-10%"  # 복습은 느리게
                
                tts_config = {
                    "text": tts_text,
                    "voice": voice,
                    "rate": rate
                }
                audio_source = None
            
            # 타이틀 설정
            title = "스피드 미리보기" if is_preview else "스피드 복습"
            
            # 무음 추가 - 쇼츠는 0.3초, 일반은 0.5초
            silence_duration = 0.3 if is_shorts else 0.5
            
            # 실제 duration 계산 (오디오/TTS 길이는 자동으로 계산되므로, 무음만 추가)
            if use_original_audio and duration:
                # 원본 오디오 사용시 duration에 무음 추가
                total_duration = duration + silence_duration
            else:
                # TTS 사용시 None으로 설정하면 TTS 길이 + 무음
                total_duration = None
            
            # 스터디 클립 생성 (subprocess로 별도 프로세스에서 실행)
            import subprocess
            import json
            
            # 임시 스크립트 생성
            script_content = f"""
import sys
sys.path.insert(0, {json.dumps(str(Path(__file__).parent))})

import asyncio
from img_tts_generator import ImgTTSGenerator

async def main():
    generator = ImgTTSGenerator()
    result = await generator.create_video(
        video_frame={{
            "path": {json.dumps(input_path)},
            "time": {extract_time},
            "crop": {json.dumps(crop_filter) if crop_filter else 'None'}
        }},
        texts={json.dumps(texts)},
        tts_config={json.dumps(tts_config) if tts_config else 'None'},
        audio_source={json.dumps(audio_source) if audio_source else 'None'},
        output_path={json.dumps(output_path)},
        resolution={resolution},
        style_preset={json.dumps("shorts" if is_shorts else "subtitle")},
        add_silence={silence_duration}
    )
    print("SUCCESS" if result else "FAILED")

asyncio.run(main())
"""
            
            # 임시 파일에 스크립트 저장
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            try:
                # 별도 프로세스에서 실행
                result = subprocess.run(
                    ['python', script_path],
                    capture_output=True,
                    text=True
                )
                
                # 결과 확인
                if result.returncode == 0 and "SUCCESS" in result.stdout:
                    return True
                else:
                    logger.error(f"Study clip generation failed: {result.stderr}")
                    return False
            finally:
                # 임시 스크립트 삭제
                import os
                os.unlink(script_path)
            
        except Exception as e:
            logger.error(f"Error creating study clip: {e}", exc_info=True)
            return False
    
    def _encode_slow_motion_clip(self, input_path: str, output_path: str,
                                start_time: float = None, duration: float = None,
                                subtitle_file: str = None, speed: float = 0.7) -> bool:
        """슬로우 모션 클립 생성"""
        cmd = ['ffmpeg', '-y']
        
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', input_path])
        
        if duration is not None:
            # 슬로우 모션이므로 실제 입력 길이는 더 짧음
            input_duration = duration / speed
            cmd.extend(['-t', str(input_duration)])
        
        # 비디오/오디오 필터
        vf_filters = []
        af_filters = []
        
        # 속도 조절 필터
        vf_filters.append(f"setpts={1/speed}*PTS")
        af_filters.append(f"atempo={speed}")
        
        # 자막 추가
        if subtitle_file and os.path.exists(subtitle_file):
            subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
            vf_filters.append(f"ass='{subtitle_path}'")
        
        # 타이틀 추가
        title_filter = self._get_title_filter()
        if title_filter:
            vf_filters.append(title_filter)
        
        if vf_filters:
            cmd.extend(['-vf', ','.join(vf_filters)])
        
        if af_filters:
            cmd.extend(['-af', ','.join(af_filters)])
        
        # 인코딩 설정
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '22',
            '-profile:v', 'high',
            '-level', '4.1',
            '-pix_fmt', 'yuv420p',
            '-tune', 'film',
            '-x264opts', 'keyint=240:min-keyint=24:scenecut=40',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            output_path
        ])
        
        returncode, stdout, stderr = self._run_ffmpeg_with_timeout(cmd)
        
        if returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            return False
        
        return True
