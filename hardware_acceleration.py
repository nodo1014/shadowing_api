"""
Hardware Acceleration Configuration
하드웨어 가속 설정을 관리하는 모듈
"""

import subprocess
import logging

logger = logging.getLogger(__name__)

class HardwareAcceleration:
    """하드웨어 가속 감지 및 설정"""
    
    @staticmethod
    def detect_nvidia_gpu():
        """NVIDIA GPU 감지"""
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def detect_vaapi():
        """Intel VAAPI 지원 감지"""
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def get_encoding_params(use_hw=True):
        """하드웨어 가속 인코딩 파라미터 반환"""
        
        if use_hw:
            # NVIDIA GPU 사용 가능한 경우
            if HardwareAcceleration.detect_nvidia_gpu():
                logger.info("NVIDIA GPU detected - using NVENC")
                return {
                    'codec': 'h264_nvenc',
                    'preset': 'p4',  # fast와 유사
                    'extra_params': ['-gpu', '0', '-b:v', '5M']
                }
            
            # Intel VAAPI 사용 가능한 경우
            elif HardwareAcceleration.detect_vaapi():
                logger.info("Intel VAAPI detected")
                return {
                    'codec': 'h264_vaapi',
                    'preset': None,
                    'extra_params': ['-vaapi_device', '/dev/dri/renderD128']
                }
        
        # CPU 인코딩 (기본값)
        logger.info("Using CPU encoding")
        return {
            'codec': 'libx264',
            'preset': 'fast',
            'extra_params': ['-threads', '0']  # 모든 CPU 코어 사용
        }

# 전역 설정
HW_ACCEL_ENABLED = True
ENCODING_PARAMS = HardwareAcceleration.get_encoding_params(HW_ACCEL_ENABLED)