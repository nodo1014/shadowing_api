# Video Clipping Service 데이터베이스 설계

## 1. 현재 문제점
- 생성된 파일 정보가 DB에 체계적으로 저장되지 않음
- 개별 클립 정보가 관리되지 않음
- 검색 및 필터링이 어려움
- 사용 통계 파악이 힘듦

## 2. 새로운 DB 스키마 설계

### 2.1 기본 원칙
- 정규화를 통한 중복 제거
- 확장성 고려 (향후 사용자 시스템 추가 가능)
- 검색 성능 최적화
- 파일 시스템과의 일관성 유지

### 2.2 테이블 구조

#### 1) jobs 테이블 (작업 관리)
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,  -- UUID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 상태 관리
    status TEXT NOT NULL,  -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,
    message TEXT,
    error_message TEXT,
    
    -- 작업 타입
    job_type TEXT NOT NULL,  -- single, batch, mixed, extract
    
    -- API 요청 정보
    api_endpoint TEXT NOT NULL,  -- /api/clip, /api/batch, etc.
    request_method TEXT DEFAULT 'POST',
    request_headers JSON,  -- User-Agent, Referer 등
    request_body JSON,  -- 원본 요청 데이터
    
    -- 요청 출처
    client_ip TEXT,
    user_agent TEXT,
    referer TEXT,
    origin TEXT,  -- CORS origin
    
    -- 입력 정보
    template_id INTEGER,
    start_time REAL,
    end_time REAL,
    duration REAL,
    
    -- 사용자 정보
    user_id TEXT,
    api_key TEXT,  -- API 키 (있는 경우)
    
    -- 처리 시간
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_duration REAL,  -- 초 단위
    
    -- 메타데이터
    metadata JSON,  -- 추가 정보 저장용
    
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_created (created_at),
    INDEX idx_jobs_user (user_id),
    INDEX idx_jobs_endpoint (api_endpoint),
    INDEX idx_jobs_client_ip (client_ip)
);
```

#### 2) templates 테이블 (템플릿 정보)
```sql
CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- shorts, general, study
    resolution_width INTEGER,
    resolution_height INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 템플릿 설정
    config JSON,  -- 템플릿별 세부 설정
    
    INDEX idx_templates_category (category)
);
```

#### 3) media_sources 테이블 (원본 미디어)
```sql
CREATE TABLE media_sources (
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
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_media_job (job_id)
);
```

#### 4) subtitles 테이블 (자막 정보)
```sql
CREATE TABLE subtitles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    -- 자막 내용
    text_eng TEXT,
    text_kor TEXT,
    note TEXT,
    keywords JSON,
    
    -- 타이밍 정보
    start_time REAL,
    end_time REAL,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_subtitles_job (job_id)
);
```

#### 5) output_videos 테이블 (생성된 비디오)
```sql
CREATE TABLE output_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    -- 비디오 타입
    video_type TEXT NOT NULL,  -- final, individual, preview, review
    clip_index INTEGER,  -- individual 클립인 경우 순서
    
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
    effect_type TEXT,  -- blur, crop, fit, none
    subtitle_mode TEXT,  -- nosub, korean, both
    
    -- 생성 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time REAL,  -- 처리 소요 시간(초)
    
    -- 뷰 정보 (YouTube 뷰어용)
    view_count INTEGER DEFAULT 0,
    last_viewed_at TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_output_job (job_id),
    INDEX idx_output_type (video_type),
    INDEX idx_output_created (created_at)
);
```

#### 6) video_segments 테이블 (비디오 구간 정보)
```sql
CREATE TABLE video_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    output_video_id INTEGER NOT NULL,
    
    -- 구간 정보
    segment_type TEXT,  -- intro, main, outro, review
    start_time REAL,
    end_time REAL,
    
    -- 구간별 설정
    audio_source TEXT,  -- original, tts, mixed
    tts_voice TEXT,
    tts_speed REAL,
    
    FOREIGN KEY (output_video_id) REFERENCES output_videos(id),
    INDEX idx_segments_video (output_video_id)
);
```

#### 7) processing_logs 테이블 (처리 로그)
```sql
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT,  -- info, warning, error
    stage TEXT,  -- download, encode, subtitle, concat, upload
    message TEXT,
    details JSON,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_logs_job (job_id),
    INDEX idx_logs_timestamp (timestamp)
);
```

#### 8) analytics 테이블 (사용 통계)
```sql
CREATE TABLE analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 집계 정보
    date DATE NOT NULL,
    hour INTEGER,  -- 0-23
    
    -- 통계
    job_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    total_duration REAL DEFAULT 0,  -- 총 비디오 길이
    total_file_size INTEGER DEFAULT 0,  -- 총 파일 크기
    
    -- 템플릿별 통계
    template_stats JSON,  -- {template_id: count}
    
    -- 성능 통계
    avg_processing_time REAL,
    max_processing_time REAL,
    
    UNIQUE(date, hour),
    INDEX idx_analytics_date (date)
);
```

#### 9) api_requests 테이블 (API 요청 추적)
```sql
CREATE TABLE api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,  -- 연관된 작업 ID (있는 경우)
    
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
    request_headers JSON,
    request_body JSON,
    query_params JSON,
    
    -- 응답 정보
    response_status INTEGER,
    response_time_ms INTEGER,  -- 응답 시간 (밀리초)
    response_body JSON,
    
    -- 인증 정보
    auth_type TEXT,  -- none, api_key, jwt
    auth_user_id TEXT,
    
    -- 에러 정보
    error_code TEXT,
    error_message TEXT,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_requests_timestamp (timestamp),
    INDEX idx_requests_endpoint (endpoint),
    INDEX idx_requests_client_ip (client_ip),
    INDEX idx_requests_job (job_id)
);
```

#### 10) rate_limits 테이블 (요청 제한 관리)
```sql
CREATE TABLE rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 식별자
    identifier TEXT NOT NULL,  -- IP 주소 또는 API 키
    identifier_type TEXT NOT NULL,  -- ip, api_key, user_id
    
    -- 제한 정보
    endpoint TEXT,  -- 특정 엔드포인트 (NULL이면 전체)
    
    -- 카운터
    request_count INTEGER DEFAULT 0,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_duration_seconds INTEGER DEFAULT 3600,  -- 기본 1시간
    
    -- 제한 설정
    limit_per_window INTEGER DEFAULT 100,
    
    -- 상태
    is_blocked BOOLEAN DEFAULT FALSE,
    blocked_until TIMESTAMP,
    block_reason TEXT,
    
    UNIQUE(identifier, identifier_type, endpoint),
    INDEX idx_rate_limits_identifier (identifier),
    INDEX idx_rate_limits_window (window_start)
);
```

#### 11) file_deletion_logs 테이블 (파일 삭제 기록)
```sql
CREATE TABLE file_deletion_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 삭제된 파일 정보
    job_id TEXT,
    output_video_id INTEGER,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    
    -- 삭제 정보
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_by TEXT,  -- 사용자 ID 또는 시스템
    deletion_reason TEXT,  -- manual, expired, storage_limit, error
    
    -- 백업 정보
    is_backed_up BOOLEAN DEFAULT FALSE,
    backup_location TEXT,
    
    -- 메타데이터 (삭제 전 정보 보존)
    metadata JSON,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    INDEX idx_deletion_logs_job (job_id),
    INDEX idx_deletion_logs_deleted_at (deleted_at)
);
```

#### 12) retention_policies 테이블 (보관 정책)
```sql
CREATE TABLE retention_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 정책 정보
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- 조건
    condition_type TEXT NOT NULL,  -- age, size, template, status
    condition_value JSON,  -- {days: 30}, {size_mb: 1000}, etc.
    
    -- 동작
    action TEXT NOT NULL,  -- delete, archive, compress
    action_params JSON,
    
    -- 실행 정보
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 3. 주요 개선사항

### 3.1 파일 추적
- 모든 생성된 파일이 `output_videos` 테이블에 기록됨
- 파일 경로, 크기, 미디어 정보 등 상세 정보 저장
- 개별 클립도 각각의 레코드로 관리

### 3.2 검색 및 필터링
- 자막 내용으로 검색 가능
- 템플릿, 날짜, 상태별 필터링
- 비디오 타입별 조회

### 3.3 통계 및 분석
- 일별/시간별 사용량 통계
- 템플릿별 인기도 파악
- 처리 성능 모니터링

### 3.4 YouTube 뷰어 통합
- 조회수 추적
- 최근 시청 시간 기록
- 인기 영상 파악

## 4. 마이그레이션 전략

### 4.1 단계별 접근
1. 새 테이블 생성 (기존 테이블 유지)
2. 새 작업부터 신규 스키마에 저장
3. 기존 데이터 마이그레이션 스크립트 실행
4. 애플리케이션 코드 업데이트
5. 이전 테이블 제거

### 4.2 데이터 무결성
- 파일 시스템과 DB 동기화 검증
- 누락된 파일/레코드 감지
- 자동 복구 메커니즘

## 5. 인덱스 전략
- 자주 사용되는 쿼리 패턴에 맞춘 인덱스
- 복합 인덱스로 조인 성능 최적화
- 정기적인 인덱스 리빌드

## 6. 파일 관리 및 삭제 기능

### 6.1 필터링 기능
- **날짜 범위**: 생성일, 최종 수정일 기준
- **파일 크기**: 특정 크기 이상/이하
- **템플릿**: 특정 템플릿으로 생성된 영상
- **상태**: 완료/실패/처리중
- **자막 내용**: 텍스트 검색
- **효과 타입**: blur, crop, fit 등
- **비디오 타입**: final, individual, preview

### 6.2 일괄 삭제 작업
```sql
-- 예시: 30일 이상된 파일 삭제
DELETE FROM output_videos 
WHERE created_at < datetime('now', '-30 days')
AND video_type = 'individual';

-- 예시: 특정 템플릿의 실패한 작업 삭제
DELETE FROM jobs
WHERE template_id = 5 
AND status = 'failed';
```

### 6.3 안전한 삭제 프로세스
1. **삭제 전 확인**: 삭제할 파일 목록 미리보기
2. **백업 옵션**: 중요 파일은 백업 후 삭제
3. **삭제 로그**: 모든 삭제 작업 기록
4. **복구 기능**: 일정 기간 내 복구 가능 (휴지통 개념)
5. **종속성 체크**: 관련 파일 함께 삭제

### 6.4 자동 정리 기능
- **일일 정리**: 매일 자정 임시 파일 삭제
- **주간 정리**: 매주 오래된 개별 클립 삭제
- **용량 기반**: 디스크 사용률 80% 초과 시 자동 정리
- **에러 정리**: 실패한 작업의 불완전한 파일 제거

## 7. API 엔드포인트 설계 (파일 관리)

### 7.1 조회 API
```
GET /api/videos/search
  - 필터 파라미터: date_from, date_to, template_id, status, text_search
  - 페이징: page, per_page
  - 정렬: sort_by, order
```

### 7.2 삭제 API
```
DELETE /api/videos/batch
  - body: {video_ids: [...], backup: true/false}
  
DELETE /api/jobs/{job_id}/cascade
  - 작업과 관련된 모든 파일 삭제
```

### 7.3 정리 API
```
POST /api/maintenance/cleanup
  - body: {type: "age"|"size"|"failed", params: {...}}
  
GET /api/maintenance/storage
  - 스토리지 사용 현황 조회
```

## 8. 향후 확장 고려사항
- 사용자 시스템 추가 시 users 테이블 추가
- 태깅 시스템 (tags, video_tags 테이블)
- 즐겨찾기 기능
- 공유 링크 관리
- S3 등 외부 스토리지 연동 정보
- 버전 관리 (동일 소스의 여러 버전)
- 워터마크 관리
- 라이선스 정보