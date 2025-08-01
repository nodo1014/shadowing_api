# Video Clipping Service

전문적인 비디오 클리핑 RESTful API 서비스 with 웹 인터페이스

## 특징

- 🎬 비디오 클리핑 with 자막 지원
- 🌐 RESTful API
- 💻 웹 기반 인터페이스
- 📦 단일 클립 및 배치 처리 지원
- 🔤 키워드 블랭킹 기능
- ⚡ 비동기 처리

## 설치

### 요구사항

- Python 3.7+
- FFmpeg (시스템에 설치 필요)

### 의존성 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
# 기본 실행 (포트 8080)
python3 clipping_api.py

# 또는 uvicorn으로 실행
uvicorn clipping_api:app --reload --port 8080
```

## 사용 방법

### 웹 인터페이스

1. 브라우저에서 `http://localhost:8080` 접속
2. 단일 클립 또는 배치 클립 모드 선택
3. 필요한 정보 입력 후 클립 생성
4. 작업 완료 후 다운로드

### API 직접 사용

API 문서: `api_documentation.md` 참조

#### 단일 클립 생성
```bash
curl -X POST http://localhost:8080/api/clip \
  -H "Content-Type: application/json" \
  -d '{
    "media_path": "/path/to/video.mp4",
    "start_time": 10.5,
    "end_time": 15.5,
    "text_eng": "Hello world",
    "text_kor": "안녕하세요",
    "clipping_type": 1
  }'
```

## 클리핑 타입

### Type 1: 기본 패턴
- 무자막 × 2회
- 영한자막 × 2회

### Type 2: 확장 패턴
- 무자막 × 2회
- 키워드 블랭크 × 2회
- 영한자막+노트 × 2회

## 프로젝트 구조

```
.
├── clipping_api.py      # FastAPI 서버
├── index.html           # 웹 인터페이스
├── styles.css           # 스타일시트
├── app.js              # 프론트엔드 로직
├── ass_generator.py     # 자막 생성 모듈
├── video_encoder.py     # 비디오 인코딩 모듈
├── requirements.txt     # Python 의존성
└── output/             # 생성된 클립 저장
```

## API 엔드포인트

- `GET /` - 웹 인터페이스
- `GET /api` - API 상태 확인
- `POST /api/clip` - 단일 클립 생성
- `POST /api/clip/batch` - 배치 클립 생성
- `GET /api/status/{job_id}` - 작업 상태 확인
- `GET /api/download/{job_id}` - 클립 다운로드
- `DELETE /api/job/{job_id}` - 작업 삭제

## 라이선스

This project is for educational purposes.