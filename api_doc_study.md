# Study Mode API Documentation

## API Parameter

`study` (Optional[str]): 학습 모드 설정
- `null` or omitted: 학습 클립 생성 안함 (기본값)
- `"preview"`: 스피드 미리보기 - 학습 클립을 맨 앞에 추가
- `"review"`: 스피드 복습 - 학습 클립을 맨 뒤에 추가

## Examples

### 1. 일반 클립만 생성 (study 없음)
```json
{
  "media_path": "/path/to/video.mp4",
  "template_number": 11,
  "clips": [...],
  "title_1": "영어 표현 학습"
}
```

### 2. 미리보기 모드 (맨 앞에 추가)
```json
{
  "media_path": "/path/to/video.mp4",
  "template_number": 11,
  "clips": [...],
  "title_1": "영어 표현 학습",
  "study": "preview"
}
```
결과: [스피드 미리보기] → [클립1] → [클립2] → ... → [통합비디오]

### 3. 복습 모드 (맨 뒤에 추가)
```json
{
  "media_path": "/path/to/video.mp4",
  "template_number": 11,
  "clips": [...],
  "title_1": "영어 표현 학습",
  "study": "review"
}
```
결과: [클립1] → [클립2] → ... → [스피드 복습] → [통합비디오]

## Study 클립 특징
- 검은 배경에 흰색 텍스트
- 각 클립의 영어/한국어 자막 표시
- Edge TTS를 사용한 음성 지원
- 약 5초 내외의 길이로 제한 (메모리 효율성)