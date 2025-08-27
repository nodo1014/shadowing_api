#!/usr/bin/env python3
"""
자막 삽입 문제 디버깅 스크립트
"""
import os
import tempfile
from ass_generator import ASSGenerator
from video_encoder import VideoEncoder

def test_subtitle_generation():
    print("=== 자막 생성 테스트 ===")
    
    # 1. ASS 파일 생성 테스트
    ass_gen = ASSGenerator()
    test_subtitle = {
        'start_time': 0.0,
        'end_time': 5.0,
        'eng': 'Hello, this is a test',
        'kor': '안녕하세요, 이것은 테스트입니다',
        'english': 'Hello, this is a test',
        'korean': '안녕하세요, 이것은 테스트입니다',
        'note': '테스트 노트'
    }
    
    with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as tmp_ass:
        ass_gen.generate_ass([test_subtitle], tmp_ass.name)
        print(f"ASS 파일 생성됨: {tmp_ass.name}")
        
        # ASS 파일 내용 확인
        with open(tmp_ass.name, 'r', encoding='utf-8') as f:
            content = f.read()
            print("\nASS 파일 내용:")
            print(content[:500])  # 처음 500자만 출력
            
        # ASS 파일에 자막이 포함되어 있는지 확인
        if 'Hello, this is a test' in content:
            print("✓ 영어 자막이 ASS 파일에 포함됨")
        else:
            print("✗ 영어 자막이 ASS 파일에 없음!")
            
        if '안녕하세요' in content:
            print("✓ 한국어 자막이 ASS 파일에 포함됨")
        else:
            print("✗ 한국어 자막이 ASS 파일에 없음!")
    
    # 2. 비디오 인코딩 명령어 테스트
    print("\n=== FFmpeg 명령어 확인 ===")
    
    # 테스트용 비디오 파일이 있는지 확인
    test_videos = [
        "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        "/tmp/test_video.mp4"
    ]
    
    test_video = None
    for video in test_videos:
        if os.path.exists(video):
            test_video = video
            break
    
    if test_video:
        print(f"테스트 비디오: {test_video}")
        
        # VideoEncoder의 _build_ffmpeg_command 메소드 직접 테스트
        encoder = VideoEncoder()
        
        # 테스트용 설정
        settings = encoder.encoding_settings['nosub_still']
        output_file = "/tmp/test_subtitle_output.mp4"
        
        # FFmpeg 명령어 생성 (내부 메소드이므로 직접 구현)
        cmd = ['ffmpeg', '-ss', '0', '-i', test_video, '-t', '5']
        
        # 비디오 필터 with 자막
        video_filter = f"scale={settings['width']}:{settings['height']}"
        abs_path = os.path.abspath(tmp_ass.name)
        escaped_path = abs_path.replace('\\', '/').replace(':', '\\:')
        font_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'font'))
        escaped_font_dir = font_dir.replace('\\', '/').replace(':', '\\:')
        video_filter = f"{video_filter},ass={escaped_path}:fontsdir={escaped_font_dir}"
        
        cmd.extend(['-vf', video_filter])
        cmd.extend(['-c:v', 'libx264', '-preset', 'slow', '-crf', '22'])
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
        cmd.extend(['-y', output_file])
        
        print("\nFFmpeg 명령어:")
        print(' '.join(cmd))
        
        # 폰트 디렉토리 확인
        print(f"\n폰트 디렉토리 존재 여부: {os.path.exists(font_dir)}")
        if os.path.exists(font_dir):
            fonts = os.listdir(font_dir)
            print(f"폰트 파일들: {fonts}")
    else:
        print("테스트용 비디오 파일을 찾을 수 없습니다.")
    
    # 정리
    if 'tmp_ass' in locals():
        os.unlink(tmp_ass.name)
        print(f"\n임시 ASS 파일 삭제됨: {tmp_ass.name}")

if __name__ == "__main__":
    test_subtitle_generation()