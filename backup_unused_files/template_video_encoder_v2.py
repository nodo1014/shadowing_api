"""
개선된 정지화면 생성 로직 테스트
"""
import subprocess
import tempfile
import os

def create_still_frame_simple(input_path, output_path, start_time, duration, subtitle_file=None):
    """
    더 간단하고 안정적인 정지화면 생성
    """
    try:
        # 1단계: 정확한 시점의 이미지 추출
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
            img_path = img_file.name
        
        # 시작 시점에서 0.1초 후의 프레임 추출 (더 안정적)
        extract_time = start_time + 0.1
        
        cmd_extract = [
            'ffmpeg', '-y',
            '-ss', str(extract_time),
            '-i', input_path,
            '-vframes', '1',
            '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
            '-q:v', '2',
            img_path
        ]
        
        print(f"Extracting frame at {extract_time}s...")
        result = subprocess.run(cmd_extract, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Frame extraction error: {result.stderr}")
            return False
        
        # 2단계: 추출한 이미지와 오디오를 결합
        cmd_combine = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', img_path,
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '44100',
            '-ac', '2',
            '-map', '0:v',
            '-map', '1:a',
            '-shortest'
        ]
        
        # 자막 추가
        if subtitle_file and os.path.exists(subtitle_file):
            subtitle_path = subtitle_file.replace('\\', '/').replace("'", "'\\''")
            cmd_combine.extend(['-vf', f"ass='{subtitle_path}'"])
        
        cmd_combine.append(output_path)
        
        print("Creating still frame video...")
        result = subprocess.run(cmd_combine, capture_output=True, text=True)
        
        # 임시 이미지 파일 삭제
        os.unlink(img_path)
        
        if result.returncode != 0:
            print(f"Combine error: {result.stderr}")
            return False
            
        print("Still frame video created successfully!")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


# 테스트
if __name__ == "__main__":
    test_input = "/home/kang/dev_amd/shadowing_maker_xls/media/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4"
    test_output = "test_still_frame.mp4"
    
    if os.path.exists(test_input):
        success = create_still_frame_simple(test_input, test_output, 30.0, 5.0)
        if success and os.path.exists(test_output):
            # 결과 확인
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 
                                   'stream=width,height,codec_name', '-of', 'json', test_output],
                                  capture_output=True, text=True)
            print("Output info:", result.stdout)