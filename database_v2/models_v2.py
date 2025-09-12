"""
Database Models V2 - SQLAlchemy ORM Models
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, 
    DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(String, primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 상태 관리
    status = Column(String, nullable=False)  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    message = Column(Text)
    error_message = Column(Text)
    
    # 작업 타입
    job_type = Column(String, nullable=False)  # single, batch, mixed, extract
    
    # API 요청 정보
    api_endpoint = Column(String, nullable=False)
    request_method = Column(String, default='POST')
    request_headers = Column(JSON)
    request_body = Column(JSON)
    
    # 요청 출처
    client_ip = Column(String)
    user_agent = Column(String)
    referer = Column(String)
    origin = Column(String)
    
    # 입력 정보
    template_id = Column(Integer, ForeignKey('templates.id'))
    start_time = Column(Float)
    end_time = Column(Float)
    duration = Column(Float)
    
    # 사용자 정보
    user_id = Column(String)
    api_key = Column(String)
    
    # 처리 시간
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_duration = Column(Float)
    
    # 메타데이터
    extra_data = Column(JSON)
    
    # Relationships
    template = relationship("Template", backref="jobs")
    media_sources = relationship("MediaSource", back_populates="job", cascade="all, delete-orphan")
    subtitles = relationship("Subtitle", back_populates="job", cascade="all, delete-orphan")
    output_videos = relationship("OutputVideo", back_populates="job", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="job", cascade="all, delete-orphan")
    api_requests = relationship("APIRequest", back_populates="job")


class Template(Base):
    __tablename__ = 'templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # shorts, general, study
    resolution_width = Column(Integer)
    resolution_height = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    config = Column(JSON)


class MediaSource(Base):
    __tablename__ = 'media_sources'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id', ondelete='CASCADE'))
    
    # 파일 정보
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    
    # 미디어 정보
    duration = Column(Float)
    width = Column(Integer)
    height = Column(Integer)
    fps = Column(Float)
    codec = Column(String)
    
    # YouTube 정보
    youtube_url = Column(String)
    youtube_title = Column(String)
    youtube_channel = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="media_sources")


class Subtitle(Base):
    __tablename__ = 'subtitles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    
    # 자막 내용
    text_eng = Column(Text)
    text_kor = Column(Text)
    note = Column(Text)
    keywords = Column(JSON)
    
    # 타이밍 정보
    start_time = Column(Float)
    end_time = Column(Float)
    
    # Relationships
    job = relationship("Job", back_populates="subtitles")


class OutputVideo(Base):
    __tablename__ = 'output_videos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    
    # 비디오 타입
    video_type = Column(String, nullable=False)  # final, individual, preview, review
    clip_index = Column(Integer)
    
    # 파일 정보
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer)
    
    # 비디오 정보
    duration = Column(Float)
    width = Column(Integer)
    height = Column(Integer)
    fps = Column(Float)
    codec = Column(String)
    bitrate = Column(Integer)
    
    # 적용된 효과
    effect_type = Column(String)  # blur, crop, fit, none
    subtitle_mode = Column(String)  # nosub, korean, both
    
    # 생성 정보
    created_at = Column(DateTime, default=datetime.utcnow)
    processing_time = Column(Float)
    
    # 뷰 정보
    view_count = Column(Integer, default=0)
    last_viewed_at = Column(DateTime)
    
    # Relationships
    job = relationship("Job", back_populates="output_videos")
    segments = relationship("VideoSegment", back_populates="output_video", cascade="all, delete-orphan")


class VideoSegment(Base):
    __tablename__ = 'video_segments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    output_video_id = Column(Integer, ForeignKey('output_videos.id', ondelete='CASCADE'), nullable=False)
    
    # 구간 정보
    segment_type = Column(String)  # intro, main, outro, review
    start_time = Column(Float)
    end_time = Column(Float)
    
    # 구간별 설정
    audio_source = Column(String)  # original, tts, mixed
    tts_voice = Column(String)
    tts_speed = Column(Float)
    
    # Relationships
    output_video = relationship("OutputVideo", back_populates="segments")


class ProcessingLog(Base):
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String)  # info, warning, error
    stage = Column(String)  # download, encode, subtitle, concat, upload
    message = Column(Text)
    details = Column(JSON)
    
    # Relationships
    job = relationship("Job", back_populates="processing_logs")


class Analytics(Base):
    __tablename__ = 'analytics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 집계 정보
    date = Column(DateTime, nullable=False)
    hour = Column(Integer)
    
    # 통계
    job_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    total_duration = Column(Float, default=0)
    total_file_size = Column(Integer, default=0)
    
    # 템플릿별 통계
    template_stats = Column(JSON)
    
    # 성능 통계
    avg_processing_time = Column(Float)
    max_processing_time = Column(Float)
    
    __table_args__ = (
        UniqueConstraint('date', 'hour'),
    )


class APIRequest(Base):
    __tablename__ = 'api_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id', ondelete='SET NULL'))
    
    # 요청 정보
    timestamp = Column(DateTime, default=datetime.utcnow)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    
    # 클라이언트 정보
    client_ip = Column(String)
    user_agent = Column(String)
    referer = Column(String)
    origin = Column(String)
    
    # 요청 데이터
    request_headers = Column(JSON)
    request_body = Column(JSON)
    query_params = Column(JSON)
    
    # 응답 정보
    response_status = Column(Integer)
    response_time_ms = Column(Integer)
    response_body = Column(JSON)
    
    # 인증 정보
    auth_type = Column(String)  # none, api_key, jwt
    auth_user_id = Column(String)
    
    # 에러 정보
    error_code = Column(String)
    error_message = Column(Text)
    
    # Relationships
    job = relationship("Job", back_populates="api_requests")


class RateLimit(Base):
    __tablename__ = 'rate_limits'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 식별자
    identifier = Column(String, nullable=False)
    identifier_type = Column(String, nullable=False)  # ip, api_key, user_id
    
    # 제한 정보
    endpoint = Column(String)
    
    # 카운터
    request_count = Column(Integer, default=0)
    window_start = Column(DateTime, default=datetime.utcnow)
    window_duration_seconds = Column(Integer, default=3600)
    
    # 제한 설정
    limit_per_window = Column(Integer, default=100)
    
    # 상태
    is_blocked = Column(Boolean, default=False)
    blocked_until = Column(DateTime)
    block_reason = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('identifier', 'identifier_type', 'endpoint'),
    )


class FileDeletionLog(Base):
    __tablename__ = 'file_deletion_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 삭제된 파일 정보
    job_id = Column(String, ForeignKey('jobs.id', ondelete='SET NULL'))
    output_video_id = Column(Integer)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    
    # 삭제 정보
    deleted_at = Column(DateTime, default=datetime.utcnow)
    deleted_by = Column(String)
    deletion_reason = Column(String)  # manual, expired, storage_limit, error
    
    # 백업 정보
    is_backed_up = Column(Boolean, default=False)
    backup_location = Column(String)
    
    # 메타데이터
    extra_data = Column(JSON)


class RetentionPolicy(Base):
    __tablename__ = 'retention_policies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 정책 정보
    name = Column(String, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # 조건
    condition_type = Column(String, nullable=False)  # age, size, template, status
    condition_value = Column(JSON)
    
    # 동작
    action = Column(String, nullable=False)  # delete, archive, compress
    action_params = Column(JSON)
    
    # 실행 정보
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database connection helper
class DatabaseManager:
    _instance = None
    _engine = None
    _SessionLocal = None
    
    def __new__(cls, db_path="clipping.db"):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._engine = create_engine(f'sqlite:///{db_path}', 
                                       connect_args={
                                           "check_same_thread": False,
                                           "timeout": 30
                                       })
            
            # Enable WAL mode for better concurrency
            from sqlalchemy import text
            with cls._engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA busy_timeout=30000"))
                conn.commit()
            
            Base.metadata.create_all(cls._engine)
            cls._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        return cls._instance
    
    @classmethod
    def get_session(cls):
        """Get a new session - use as context manager"""
        if cls._SessionLocal is None:
            # Initialize if not done
            DatabaseManager()
        
        from contextlib import contextmanager
        
        @contextmanager
        def session_scope():
            session = cls._SessionLocal()
            try:
                yield session
                session.commit()
            except:
                session.rollback()
                raise
            finally:
                session.close()
        
        return session_scope()


# Helper functions for common queries
def get_job_with_videos(session, job_id):
    """Get job with all related videos"""
    return session.query(Job).filter(Job.id == job_id).first()
    
def get_videos_by_filter(session, **filters):
    """Get videos with various filters"""
    query = session.query(OutputVideo)
    
    if 'video_type' in filters:
        query = query.filter(OutputVideo.video_type == filters['video_type'])
    
    if 'created_after' in filters:
        query = query.filter(OutputVideo.created_at >= filters['created_after'])
        
    if 'created_before' in filters:
        query = query.filter(OutputVideo.created_at <= filters['created_before'])
        
    if 'template_id' in filters:
        query = query.join(Job).filter(Job.template_id == filters['template_id'])
        
    return query.all()
    
def log_api_request(session, request_data):
    """Log an API request"""
    api_request = APIRequest(**request_data)
    session.add(api_request)
    session.commit()
    return api_request