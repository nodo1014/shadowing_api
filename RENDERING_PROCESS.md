# Shadowing Maker 렌더링 프로세스 문서

## 1. ASS 자막 생성 로직

### ass_generator.py
```python
# 스타일 정의
styles = {
    "english": {
        "font_size": 28,
        "primary_color": "&HFFFFFF&",  # 흰색
        "outline": 1
    },
    "korean": {
        "font_size": 24,
        "primary_color": "&H00FFFF&",  # 노란색
        "outline": 1
    },
    "note": {
        "font_size": 24,
        "primary_color": "&H00FFFF&",  # 노란색
        "alignment": 7  # 왼쪽 상단
    }
}

# 키워드 하이라이팅
keyword_color = "&H0080FF&"  # 오렌지색
```

### subtitle_generator.py
- `generate_full_subtitle()`: 완전한 영한 자막
- `generate_blank_subtitle()`: 키워드를 ___로 치환
- `generate_korean_only_subtitle()`: 한글만 표시

## 2. FFmpeg 최적화 옵션 (유지 필수)

```bash
# 비디오 인코딩
-c:v libx264
-preset medium       # 품질/속도 균형
-crf 16             # 높은 품질
-profile:v high
-level 4.1
-pix_fmt yuv420p
-tune film          # 영화/드라마 최적화

# 오디오 인코딩
-c:a aac
-b:a 192k
-af aresample=async=1  # 오디오 동기화

# 추가 옵션
-x264opts keyint=240:min-keyint=24:scenecut=40
-movflags +faststart   # 웹 스트리밍 최적화
```

## 3. 템플릿 시스템 구조

### 현재 템플릿
1. **Template 1**: Basic (무자막 2회 → 영한자막 2회)
2. **Template 2**: Keyword (무자막 1회 → 블랭크 1회 → 영한+키워드 2회)
3. **Template 3**: Progressive (무자막 2회 → 블랭크+한글 2회 → 영한자막 2회)
4. **Template 4**: Template 3 복사본 (확장 가능)

### 템플릿 정의 구조
```json
{
  "template_name": {
    "name": "표시 이름",
    "description": "설명",
    "clips": [
      {
        "subtitle_mode": "표시용 이름",
        "folder_name": "저장 폴더명",
        "count": 반복 횟수,
        "subtitle_type": "자막 타입 (null|full|blank|blank_korean)"
      }
    ],
    "gap_duration": 갭 길이(초)
  }
}
```

## 4. 새 템플릿 추가 가이드

### Step 1: templates/shadowing_patterns.json 수정
```json
"template_5": {
  "name": "새 템플릿 이름",
  "description": "설명",
  "clips": [...],
  "gap_duration": 2.0
}
```

### Step 2: 새 subtitle_type 필요 시
1. `subtitle_generator.py`에 생성 메서드 추가
2. `template_video_encoder.py`의 `_prepare_subtitle_files()` 수정

### Step 3: API 업데이트
- `clipping_api.py`의 template_number 범위 확장

## 5. 프로세싱 플로우

```
API 요청
  ↓
템플릿 로드
  ↓
자막 파일 생성 (ASS)
  ↓
각 클립 인코딩 (FFmpeg)
  ↓
갭 추가 (freeze frame)
  ↓
클립 연결 (concat)
  ↓
출력 저장
```

## 6. 확장 가능한 subtitle_type 아이디어

- `english_only`: 영어만
- `phonetic`: 발음 기호 포함
- `word_by_word`: 단어별 순차 표시
- `highlighted`: 특정 단어 강조
- `slow_fade`: 페이드 효과

## 7. 성능 고려사항

- 클립 수 ↑ = 처리 시간 ↑
- CRF 값 ↓ = 품질 ↑, 파일 크기 ↑
- 갭 생성 = 추가 연산 필요
- 개별 클립 저장 = 디스크 공간 사용

## 8. 디버깅 로그

- `[ASS DEBUG]`: ASS 생성 과정
- `[BLANK DEBUG]`: 블랭크 처리 과정
- `[DEBUG]`: 갭 생성 및 연결 과정