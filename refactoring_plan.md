# 리팩토링 계획

## 현재 파일 크기 및 문제점
- clipping_api.py: 1531줄 (너무 크고 복잡)
- video_encoder.py: 840줄 (여러 책임이 혼재)
- database.py: 341줄 (적절하지만 분리 가능)

## 새로운 디렉토리 구조

```
shadowing_maker/
├── __init__.py
├── api/                      # FastAPI 관련
│   ├── __init__.py
│   ├── app.py              # FastAPI 앱 초기화
│   ├── routes/             # API 엔드포인트
│   │   ├── __init__.py
│   │   ├── clip.py        # 클리핑 관련 라우트
│   │   ├── admin.py       # 관리자 라우트
│   │   ├── job.py         # 작업 상태/다운로드
│   │   ├── batch.py       # 배치 처리
│   │   └── health.py      # 헬스체크
│   ├── models/             # Pydantic 모델
│   │   ├── __init__.py
│   │   ├── requests.py    # 요청 모델
│   │   └── responses.py   # 응답 모델
│   └── middleware/         # 미들웨어
│       ├── __init__.py
│       ├── cors.py        # CORS 설정
│       └── rate_limit.py  # Rate limiting
│
├── core/                   # 핵심 비즈니스 로직
│   ├── __init__.py
│   ├── video/             # 비디오 처리
│   │   ├── __init__.py
│   │   ├── encoder.py     # 기본 인코딩
│   │   ├── template_encoder.py # 템플릿 인코딩
│   │   ├── ffmpeg_utils.py    # FFmpeg 유틸
│   │   └── concatenator.py    # 비디오 연결
│   ├── subtitle/          # 자막 처리
│   │   ├── __init__.py
│   │   ├── generator.py   # 자막 생성
│   │   └── ass_creator.py # ASS 파일 생성
│   └── tasks/             # 백그라운드 작업
│       ├── __init__.py
│       ├── clip_processor.py
│       └── batch_processor.py
│
├── database/              # 데이터베이스 관련
│   ├── __init__.py
│   ├── models.py         # SQLAlchemy 모델
│   ├── connection.py     # DB 연결 관리
│   └── repositories/     # 저장소 패턴
│       ├── __init__.py
│       ├── job_repo.py   # Job 저장소
│       └── batch_repo.py # Batch 저장소
│
├── utils/                # 유틸리티
│   ├── __init__.py
│   ├── config.py        # 설정 관리
│   ├── logger.py        # 로깅
│   └── exceptions.py    # 커스텀 예외
│
└── templates/           # 템플릿 파일
    └── shadowing_patterns.json
```

## 리팩토링 단계

### Phase 1: 디렉토리 구조 생성 ✅
### Phase 2: API 라우트 분리
### Phase 3: 비디오 처리 로직 분리
### Phase 4: 데이터베이스 레이어 분리
### Phase 5: 유틸리티 정리
### Phase 6: 테스트 및 검증