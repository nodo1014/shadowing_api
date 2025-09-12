-- Video Clipping Service Database Schema V2
-- SQLite3 compatible

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- 1. Jobs table (작업 관리)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,  -- UUID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 상태 관리
    status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    progress INTEGER DEFAULT 0,
    message TEXT,
    error_message TEXT,
    
    -- 작업 타입
    job_type TEXT NOT NULL CHECK(job_type IN ('single', 'batch', 'mixed', 'extract')),
    
    -- API 요청 정보
    api_endpoint TEXT NOT NULL,
    request_method TEXT DEFAULT 'POST',
    request_headers TEXT,  -- JSON
    request_body TEXT,     -- JSON
    
    -- 요청 출처
    client_ip TEXT,
    user_agent TEXT,
    referer TEXT,
    origin TEXT,
    
    -- 입력 정보
    template_id INTEGER,
    start_time REAL,
    end_time REAL,
    duration REAL,
    
    -- 사용자 정보
    user_id TEXT,
    api_key TEXT,
    
    -- 처리 시간
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_duration REAL,
    
    -- 메타데이터
    extra_data TEXT  -- JSON
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at);
CREATE INDEX idx_jobs_user ON jobs(user_id);
CREATE INDEX idx_jobs_endpoint ON jobs(api_endpoint);
CREATE INDEX idx_jobs_client_ip ON jobs(client_ip);

-- 2. Templates table (템플릿 정보)
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT CHECK(category IN ('shorts', 'general', 'study')),
    resolution_width INTEGER,
    resolution_height INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config TEXT  -- JSON
);

CREATE INDEX idx_templates_category ON templates(category);

-- 3. Media sources table (원본 미디어)
CREATE TABLE IF NOT EXISTS media_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    
    -- 파일 정보
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    
    -- 미디어 정보
    duration REAL,
    width INTEGER,
    height INTEGER,
    fps REAL,
    codec TEXT,
    
    -- YouTube 정보 (있는 경우)
    youtube_url TEXT,
    youtube_title TEXT,
    youtube_channel TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_media_job ON media_sources(job_id);

-- 4. Subtitles table (자막 정보)
CREATE TABLE IF NOT EXISTS subtitles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    -- 자막 내용
    text_eng TEXT,
    text_kor TEXT,
    note TEXT,
    keywords TEXT,  -- JSON
    
    -- 타이밍 정보
    start_time REAL,
    end_time REAL,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_subtitles_job ON subtitles(job_id);

-- 5. Output videos table (생성된 비디오)
CREATE TABLE IF NOT EXISTS output_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    -- 비디오 타입
    video_type TEXT NOT NULL CHECK(video_type IN ('final', 'individual', 'preview', 'review')),
    clip_index INTEGER,
    
    -- 파일 정보
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    
    -- 비디오 정보
    duration REAL,
    width INTEGER,
    height INTEGER,
    fps REAL,
    codec TEXT,
    bitrate INTEGER,
    
    -- 적용된 효과
    effect_type TEXT CHECK(effect_type IN ('blur', 'crop', 'fit', 'none')),
    subtitle_mode TEXT CHECK(subtitle_mode IN ('nosub', 'korean', 'both')),
    
    -- 생성 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time REAL,
    
    -- 뷰 정보 (YouTube 뷰어용)
    view_count INTEGER DEFAULT 0,
    last_viewed_at TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_output_job ON output_videos(job_id);
CREATE INDEX idx_output_type ON output_videos(video_type);
CREATE INDEX idx_output_created ON output_videos(created_at);

-- 6. Video segments table (비디오 구간 정보)
CREATE TABLE IF NOT EXISTS video_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    output_video_id INTEGER NOT NULL,
    
    -- 구간 정보
    segment_type TEXT CHECK(segment_type IN ('intro', 'main', 'outro', 'review')),
    start_time REAL,
    end_time REAL,
    
    -- 구간별 설정
    audio_source TEXT CHECK(audio_source IN ('original', 'tts', 'mixed')),
    tts_voice TEXT,
    tts_speed REAL,
    
    FOREIGN KEY (output_video_id) REFERENCES output_videos(id) ON DELETE CASCADE
);

CREATE INDEX idx_segments_video ON video_segments(output_video_id);

-- 7. Processing logs table (처리 로그)
CREATE TABLE IF NOT EXISTS processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT CHECK(level IN ('info', 'warning', 'error')),
    stage TEXT CHECK(stage IN ('download', 'encode', 'subtitle', 'concat', 'upload')),
    message TEXT,
    details TEXT,  -- JSON
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_logs_job ON processing_logs(job_id);
CREATE INDEX idx_logs_timestamp ON processing_logs(timestamp);

-- 8. Analytics table (사용 통계)
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 집계 정보
    date DATE NOT NULL,
    hour INTEGER CHECK(hour >= 0 AND hour <= 23),
    
    -- 통계
    job_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    total_duration REAL DEFAULT 0,
    total_file_size INTEGER DEFAULT 0,
    
    -- 템플릿별 통계
    template_stats TEXT,  -- JSON
    
    -- 성능 통계
    avg_processing_time REAL,
    max_processing_time REAL,
    
    UNIQUE(date, hour)
);

CREATE INDEX idx_analytics_date ON analytics(date);

-- 9. API requests table (API 요청 추적)
CREATE TABLE IF NOT EXISTS api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    
    -- 요청 정보
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    
    -- 클라이언트 정보
    client_ip TEXT,
    user_agent TEXT,
    referer TEXT,
    origin TEXT,
    
    -- 요청 데이터
    request_headers TEXT,  -- JSON
    request_body TEXT,     -- JSON
    query_params TEXT,     -- JSON
    
    -- 응답 정보
    response_status INTEGER,
    response_time_ms INTEGER,
    response_body TEXT,    -- JSON
    
    -- 인증 정보
    auth_type TEXT CHECK(auth_type IN ('none', 'api_key', 'jwt')),
    auth_user_id TEXT,
    
    -- 에러 정보
    error_code TEXT,
    error_message TEXT,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX idx_requests_timestamp ON api_requests(timestamp);
CREATE INDEX idx_requests_endpoint ON api_requests(endpoint);
CREATE INDEX idx_requests_client_ip ON api_requests(client_ip);
CREATE INDEX idx_requests_job ON api_requests(job_id);

-- 10. Rate limits table (요청 제한 관리)
CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 식별자
    identifier TEXT NOT NULL,
    identifier_type TEXT NOT NULL CHECK(identifier_type IN ('ip', 'api_key', 'user_id')),
    
    -- 제한 정보
    endpoint TEXT,
    
    -- 카운터
    request_count INTEGER DEFAULT 0,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_duration_seconds INTEGER DEFAULT 3600,
    
    -- 제한 설정
    limit_per_window INTEGER DEFAULT 100,
    
    -- 상태
    is_blocked BOOLEAN DEFAULT 0,
    blocked_until TIMESTAMP,
    block_reason TEXT,
    
    UNIQUE(identifier, identifier_type, endpoint)
);

CREATE INDEX idx_rate_limits_identifier ON rate_limits(identifier);
CREATE INDEX idx_rate_limits_window ON rate_limits(window_start);

-- 11. File deletion logs table (파일 삭제 기록)
CREATE TABLE IF NOT EXISTS file_deletion_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 삭제된 파일 정보
    job_id TEXT,
    output_video_id INTEGER,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    
    -- 삭제 정보
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_by TEXT,
    deletion_reason TEXT CHECK(deletion_reason IN ('manual', 'expired', 'storage_limit', 'error')),
    
    -- 백업 정보
    is_backed_up BOOLEAN DEFAULT 0,
    backup_location TEXT,
    
    -- 메타데이터
    extra_data TEXT,  -- JSON
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX idx_deletion_logs_job ON file_deletion_logs(job_id);
CREATE INDEX idx_deletion_logs_deleted_at ON file_deletion_logs(deleted_at);

-- 12. Retention policies table (보관 정책)
CREATE TABLE IF NOT EXISTS retention_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 정책 정보
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    
    -- 조건
    condition_type TEXT NOT NULL CHECK(condition_type IN ('age', 'size', 'template', 'status')),
    condition_value TEXT,  -- JSON
    
    -- 동작
    action TEXT NOT NULL CHECK(action IN ('delete', 'archive', 'compress')),
    action_params TEXT,    -- JSON
    
    -- 실행 정보
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to update the updated_at timestamp
CREATE TRIGGER update_jobs_timestamp 
AFTER UPDATE ON jobs
BEGIN
    UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER update_retention_policies_timestamp
AFTER UPDATE ON retention_policies
BEGIN
    UPDATE retention_policies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;