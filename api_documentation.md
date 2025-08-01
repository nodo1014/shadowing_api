# Video Clipping API Documentation

## 개요
전문적인 비디오 클리핑 서비스를 제공하는 RESTful API입니다.

## 기본 정보
- **Base URL**: `http://localhost:8080`
- **Response Format**: JSON
- **Video Format**: MP4

## 엔드포인트

### 1. 클립 생성 요청
**POST** `/api/clip`

비디오 클립을 생성합니다.

#### Request Body
```json
{
  "media_path": "/path/to/video.mp4",
  "start_time": 10.5,
  "end_time": 15.5,
  "text_eng": "Hello, how are you?",
  "text_kor": "안녕하세요, 어떻게 지내세요?",
  "note": "인사하기",
  "keywords": ["Hello", "how"],
  "text_eng_blank": null,
  "clipping_type": 1,
  "individual_clips": false
}
```

#### 파라미터 설명
- `media_path` (string, required): 원본 비디오 파일 경로
- `start_time` (float, required): 클립 시작 시간 (초)
- `end_time` (float, required): 클립 종료 시간 (초)
- `text_eng` (string, required): 영문 자막
- `text_kor` (string, required): 한국어 번역
- `note` (string, optional): 문장 설명
- `keywords` (array, optional): 핵심 키워드 리스트
- `text_eng_blank` (string, optional): 키워드 블랭크 처리된 영문 (자동 생성 가능)
- `clipping_type` (integer, required): 클리핑 타입
  - `1`: 무자막 × 2회 + 영한자막 × 2회
  - `2`: 무자막 × 2회 + 키워드 블랭크 × 2회 + 영한자막+노트 × 2회
- `individual_clips` (boolean, optional): 개별 클립 저장 여부

#### Response
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "accepted",
  "message": "클리핑 작업이 시작되었습니다."
}
```

### 2. 작업 상태 확인
**GET** `/api/status/{job_id}`

작업 진행 상태를 확인합니다.

#### Response
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": 50,
  "message": "비디오 클리핑 중...",
  "output_file": null,
  "individual_clips": null,
  "error": null
}
```

#### 상태 값
- `pending`: 대기 중
- `processing`: 처리 중
- `completed`: 완료
- `failed`: 실패

### 3. 클립 다운로드
**GET** `/api/download/{job_id}`

생성된 클립을 다운로드합니다.

#### Response
- Content-Type: `video/mp4`
- 파일명: `clip_{job_id}.mp4`

### 4. 개별 클립 다운로드
**GET** `/api/download/{job_id}/individual/{index}`

개별 클립을 다운로드합니다.

#### Parameters
- `index`: 클립 인덱스 (0부터 시작)

### 5. 작업 삭제
**DELETE** `/api/job/{job_id}`

작업과 관련 파일을 삭제합니다.

## 클리핑 타입 상세

### Type 1: 기본 패턴
```
[무자막] → [무자막] → [영한자막] → [영한자막]
```
- 무자막 구간: 듣기 연습
- 영한자막 구간: 의미 확인

### Type 2: 키워드 학습 패턴
```
[무자막] → [무자막] → [키워드 블랭크] → [키워드 블랭크] → [영한자막+노트] → [영한자막+노트]
```
- 무자막 구간: 듣기 연습
- 키워드 블랭크 구간: 핵심 단어 추측
- 영한자막+노트 구간: 전체 의미와 설명 확인

## 키워드 블랭크 처리

키워드로 지정된 단어들은 언더스코어(`_`)로 대체됩니다.

예시:
- 원문: "Hello world, how are you today?"
- 키워드: ["Hello", "world", "today"]
- 블랭크: "_____ _____, how are you _____?"

## 사용 예시

### Python
```python
import requests

# 클립 생성 요청
data = {
    "media_path": "/path/to/video.mp4",
    "start_time": 10.5,
    "end_time": 15.5,
    "text_eng": "Hello, how are you?",
    "text_kor": "안녕하세요, 어떻게 지내세요?",
    "clipping_type": 1
}

response = requests.post("http://localhost:8080/api/clip", json=data)
job_id = response.json()["job_id"]

# 상태 확인
status = requests.get(f"http://localhost:8080/api/status/{job_id}").json()
print(f"Progress: {status['progress']}%")

# 다운로드
if status['status'] == 'completed':
    clip = requests.get(f"http://localhost:8080/api/download/{job_id}")
    with open("output.mp4", "wb") as f:
        f.write(clip.content)
```

### cURL
```bash
# 클립 생성
curl -X POST http://localhost:8080/api/clip \
  -H "Content-Type: application/json" \
  -d '{
    "media_path": "/path/to/video.mp4",
    "start_time": 10.5,
    "end_time": 15.5,
    "text_eng": "Hello",
    "text_kor": "안녕",
    "clipping_type": 1
  }'

# 상태 확인
curl http://localhost:8080/api/status/JOB_ID

# 다운로드
curl -O http://localhost:8080/api/download/JOB_ID
```

## 서버 실행

```bash
# 기본 실행 (포트 8080)
python3 clipping_api.py

# 커스텀 포트
uvicorn clipping_api:app --host 0.0.0.0 --port 8000

# 개발 모드 (자동 리로드)
uvicorn clipping_api:app --reload
```

## 요구사항

- Python 3.7+
- FastAPI
- uvicorn
- FFmpeg (시스템에 설치되어 있어야 함)

## 에러 처리

모든 에러는 다음 형식으로 반환됩니다:

```json
{
  "detail": "에러 메시지"
}
```

HTTP 상태 코드:
- `200`: 성공
- `400`: 잘못된 요청
- `404`: 리소스를 찾을 수 없음
- `500`: 서버 오류