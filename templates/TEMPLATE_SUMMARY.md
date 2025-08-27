# 템플릿 정리

## 0. 원본 구간 추출 템플릿

### template_0 (template_original) - Original Style
- **비디오 타입**: 원본 구간 추출
- **TTS 사용**: 없음
- **특징**: 
  - 학습 가공 없이 원본 그대로 추출
  - 여러 자막을 원본 타이밍 그대로 포함
  - 자막 스타일만 통일된 형식으로 적용
  - 영화 장면을 그대로 감상할 때 사용
- **용도**: 
  - 영화/드라마의 특정 구간을 추출하여 감상
  - 학습 템플릿과 혼합하여 유연한 콘텐츠 제작
  - 자막 없이 먼저 보기 → 학습 → 다시 감상 패턴

## 1. 일반용 템플릿 (16:9 가로형)

### template_1 - Progressive Learning
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(1회) → 블랭크(1회) → 블랭크+한글(1회) → 영한자막(1회) → 무자막(1회)
- **간격**: 0.5초

### template_2 - Keyword Focus  
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(1회) → 블랭크(1회) → 영한자막(2회)
- **간격**: 0.5초

### template_3 - Progressive Learning (반복형)
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(2회) → 블랭크+한글(2회) → 영한자막(2회)
- **간격**: 0.5초





## 2. 쇼츠용 템플릿 (9:16 세로형)

### template_1_shorts - Progressive Learning (Shorts)
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(1회) → 블랭크+한글(1회) → 영한자막(1회)
- **간격**: 0.3초
- **해상도**: 1080x1920

### template_2_shorts - Keyword Focus (Shorts)
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(1회) → 영한자막(2회)
- **간격**: 0.3초
- **해상도**: 1080x1920

### template_3_shorts - Progressive Learning (Shorts)
- **비디오 타입**: 일반 동영상
- **TTS 사용**: 없음
- **구성**: 무자막(1회) → 블랭크+한글(1회) → 영한자막(1회)
- **간격**: 0.3초
- **해상도**: 1080x1920

## 3. 스터디 클립 (단일 클립)

### 일반 스터디 클립 (16:9)
- **template_study_preview** (템플릿 번호 31)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 영어 TTS (en-US-AriaNeural, 정상속도)
  
- **template_study_review** (템플릿 번호 32)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 영어 TTS (en-US-AriaNeural, 느린속도 -10%)
  
- **template_study_original** (템플릿 번호 35)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 없음 (원본 오디오 추출)

### 쇼츠 스터디 클립 (9:16)
- **template_study_shorts_preview** (템플릿 번호 33)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 영어 TTS (en-US-AriaNeural, 정상속도)
  - **해상도**: 1080x1920
  
- **template_study_shorts_review** (템플릿 번호 34)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 영어 TTS (en-US-AriaNeural, 느린속도 -10%)
  - **해상도**: 1080x1920
  
- **template_study_shorts_original** (템플릿 번호 36)
  - **비디오 타입**: 정지화면
  - **TTS 사용**: 없음 (원본 오디오 추출)
  - **해상도**: 1080x1920

## 배치 모드 지원

모든 템플릿은 배치 처리를 지원하며:
- 개별 클립 저장 옵션 (`save_individual_clips=True`)
- 폴더별 자동 분류 (예: `1_nosub`, `2_blank`, `3_both`)
- 다중 클립 동시 처리
- 진행 상태 표시

## 주요 기술적 특징

### 비디오 타입
- **일반 동영상**: 원본 비디오 재생
- **정지화면**: 특정 프레임 고정 표시
- **슬로우모션**: 속도 조절 (70%)

### TTS 음성
- **영어**: Edge TTS en-US-AriaNeural
- **한국어**: Edge TTS ko-KR-SunHiNeural
- **속도 조절**: 정상속도 또는 -10% (느린속도)

## API 요청 방법

### 1. 단일 클립 생성 (/api/clip)
```json
{
    "media_path": "/path/to/video.mp4",
    "start_time": 10.5,
    "end_time": 15.0,
    "text_eng": "Hello, how are you?",
    "text_kor": "안녕하세요, 어떻게 지내세요?",
    "template_number": 1,
    "keywords": ["hello"]  // template_2에서만 사용
}
```

### 2. 배치 클립 생성 (/api/batch)
```json
{
    "media_path": "/path/to/video.mp4",
    "template_number": 1,
    "clips": [
        {
            "start_time": 10.5,
            "end_time": 15.0,
            "text_eng": "Hello",
            "text_kor": "안녕"
        },
        {
            "start_time": 20.0,
            "end_time": 23.0,
            "text_eng": "Good morning",
            "text_kor": "좋은 아침"
        }
    ],
    "title_1": "English Study",  // 옵션
    "title_2": "Episode 1"       // 옵션
}
```

### 3. 혼합 템플릿 생성 (/api/clip/mixed)
```json
{
    "media_path": "/path/to/video.mp4",
    "clips": [
        {
            "start_time": 60.0,
            "end_time": 65.0,
            "template_number": 0,
            "subtitles": [
                {
                    "start": 60.5,
                    "end": 62.0,
                    "eng": "What are you doing?",
                    "kor": "뭐 하고 있어?"
                },
                {
                    "start": 62.5,
                    "end": 64.5,
                    "eng": "I'm studying.",
                    "kor": "공부하고 있어."
                }
            ]
        },
        {
            "start_time": 70.0,
            "end_time": 73.0,
            "template_number": 1,
            "text_eng": "This is important.",
            "text_kor": "이것은 중요해."
        }
    ],
    "combine": true,
    "transitions": false
}
```

### 4. 구간 추출 (/api/extract/range)
```json
{
    "media_path": "/path/to/video.mp4",
    "start_time": 100.0,
    "end_time": 120.0,
    "template_number": 0,
    "subtitles": [
        {
            "start": 101.0,
            "end": 103.0,
            "eng": "Welcome to the show.",
            "kor": "쇼에 오신 것을 환영합니다."
        },
        {
            "start": 105.0,
            "end": 107.0,
            "eng": "Today's topic is...",
            "kor": "오늘의 주제는..."
        }
    ]
}
```

### 주요 템플릿 번호
- **0**: 원본 구간 추출 (template_original)
- **1-3**: 일반 학습 템플릿
- **11-13**: 쇼츠 템플릿
- **21-29**: TTS 템플릿
- **31-36**: 스터디 클립

### 사용 예시: 유연한 콘텐츠 제작

#### 영화 학습 콘텐츠
```json
{
    "media_path": "/path/to/movie.mp4",
    "clips": [
        // 1. 자막 없이 먼저 감상
        {
            "start_time": 300.0,
            "end_time": 310.0,
            "template_number": 0,
            "subtitles": []  // 빈 배열로 자막 없이
        },
        // 2. 핵심 문장 학습
        {
            "start_time": 303.0,
            "end_time": 305.0,
            "template_number": 2,
            "text_eng": "I need your help.",
            "text_kor": "네 도움이 필요해.",
            "keywords": ["need", "help"]
        },
        // 3. 전체 구간 다시 감상
        {
            "start_time": 300.0,
            "end_time": 310.0,
            "template_number": 0,
            "subtitles": [
                {
                    "start": 303.0,
                    "end": 305.0,
                    "eng": "I need your help.",
                    "kor": "네 도움이 필요해."
                },
                {
                    "start": 306.0,
                    "end": 308.0,
                    "eng": "What can I do?",
                    "kor": "뭘 도와줄까?"
                }
            ]
        }
    ],
    "combine": true
}
```