"""
Media and Input Validators
"""
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 허용된 미디어 루트 디렉토리
ALLOWED_MEDIA_ROOTS = [
    Path("/mnt/qnap/media_eng/indexed_media"),
    Path("/mnt/qnap/media_eng2/indexed_media"),
]


class MediaValidator:
    """미디어 파일 경로 검증"""
    
    @staticmethod
    def validate_media_path(media_path: str) -> Optional[Path]:
        """
        미디어 경로가 허용된 디렉토리 내에 있는지 확인
        """
        try:
            path = Path(media_path).resolve()
            
            # 파일 존재 확인
            if not path.exists() or not path.is_file():
                logger.warning(f"File not found: {media_path}")
                # 파일이 없어도 허용된 루트 내에 있으면 통과 (나중에 생성될 수 있음)
                for allowed_root in ALLOWED_MEDIA_ROOTS:
                    if allowed_root.exists():
                        try:
                            path.relative_to(allowed_root)
                            logger.info(f"File not found but path is in allowed directory: {media_path}")
                            return path
                        except ValueError:
                            continue
                return None
            
            # 허용된 루트 디렉토리 내에 있는지 확인
            for allowed_root in ALLOWED_MEDIA_ROOTS:
                if allowed_root.exists():
                    try:
                        # 상대 경로 계산으로 확인
                        path.relative_to(allowed_root)
                        # 지원 형식 확인
                        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.flv'}
                        if path.suffix.lower() not in allowed_extensions:
                            logger.warning(f"Unsupported format: {path.suffix}")
                            return None
                        return path
                    except ValueError:
                        continue
            
            logger.warning(f"Path not in allowed directories: {media_path}")
            return None
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return None