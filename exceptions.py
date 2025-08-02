"""
Custom exceptions for Shadowing Maker
커스텀 예외 클래스들
"""

class ShadowingMakerError(Exception):
    """Base exception for all Shadowing Maker errors"""
    pass

class VideoEncodingError(ShadowingMakerError):
    """Raised when video encoding fails"""
    pass

class SubtitleGenerationError(ShadowingMakerError):
    """Raised when subtitle generation fails"""
    pass

class MediaFileNotFoundError(ShadowingMakerError):
    """Raised when media file is not found"""
    pass

class InvalidTemplateError(ShadowingMakerError):
    """Raised when template is invalid or not found"""
    pass

class FFmpegError(VideoEncodingError):
    """Raised when FFmpeg command fails"""
    def __init__(self, message, stderr=None, returncode=None):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode

class TimeoutError(VideoEncodingError):
    """Raised when video processing times out"""
    pass

class InvalidTimeRangeError(ShadowingMakerError):
    """Raised when start/end times are invalid"""
    pass

class DatabaseError(ShadowingMakerError):
    """Raised when database operation fails"""
    pass