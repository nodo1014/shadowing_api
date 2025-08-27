# 리뷰 클립 개선사항 문서

## 개요
2024-08-26 리뷰 클립 생성기에 다음과 같은 개선사항이 적용되었습니다.

## 주요 변경사항

### 1. 폰트 개선
- **변경 전**: NotoSans Regular 또는 기본 폰트 사용
- **변경 후**: NotoSans CJK Bold 우선 사용
- **폰트 경로 우선순위**:
  ```
  1. /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc (Bold 우선)
  2. /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
  3. 기타 대체 경로들...
  ```

### 2. 텍스트 가시성 향상
- **테두리 두께**: 2px → 5px로 증가
- **효과**: 모바일 환경에서도 선명한 가독성 확보

### 3. TTS 음성 개선
- **영어 음성**: 기본 → Aria (en-US-AriaNeural)
- **속도**: 기본 → -10% (10% 느리게)
- **코드 변경**:
  ```python
  self.tts_generator = EdgeTTSGenerator(voice='en-US-AriaNeural', rate='-10%')
  ```

### 4. 배경 개선
- **변경 전**: 검은색 단색 배경
- **변경 후**: 원본 비디오의 정지 프레임 사용
- **구현 방식**:
  - 각 클립의 중간 시점에서 프레임 추출
  - 쇼츠용 크롭 필터 적용 (정사각형 → 1080x1920)
  - 추출된 프레임을 배경으로 사용

### 5. 자막 위치 (쇼츠)
- **한글 자막**: 화면 하단에서 220px 위 (h-220)
- **영어 자막**: 화면 하단에서 360px 위 (h-360)
- **색상**:
  - 한글: 골드색 (#FFD700)
  - 영어: 흰색 (white)

## 기술적 구현

### 정지 프레임 추출 메서드
```python
async def _extract_freeze_frame(self, video_path: str, time: float, 
                               crop_filter: Optional[str] = None) -> Optional[str]:
    """비디오에서 정지 프레임 추출"""
    # FFmpeg를 사용해 특정 시점의 프레임 추출
    # 크롭 필터 적용 (쇼츠용)
```

### 개선된 create_review_clip 시그니처
```python
async def create_review_clip(self, clips_data: List[Dict], output_path: str,
                            title: str = "스피드 복습", template_number: int = 11,
                            video_path: Optional[str] = None, 
                            clip_timestamps: Optional[List[Tuple[float, float]]] = None) -> bool:
```

## 사용 예시

```python
# 리뷰 클립 생성
generator = ReviewClipGenerator()
success = await generator.create_review_clip(
    clips_data=clips_data,
    output_path="review.mp4",
    title="스피드 복습",
    template_number=11,  # 쇼츠
    video_path="/path/to/original/video.mp4",  # 정지 프레임용
    clip_timestamps=[(50.0, 52.5), (53.0, 56.0)]  # 각 클립의 시간
)
```

## 장점
1. **가독성 향상**: Bold 폰트와 두꺼운 테두리로 모바일에서도 선명
2. **맥락 제공**: 원본 영상 배경으로 학습 내용 이해도 향상
3. **학습 효과**: Aria 음성과 느린 속도로 따라하기 쉬움
4. **일관성**: 메인 클립과 동일한 자막 위치 및 스타일

## 파일 변경사항
- `review_clip_generator.py`: 주요 기능 개선
- `clipping_api.py`: video_path와 clip_timestamps 전달 추가

## 테스트 결과
- 파일 크기: 약 350KB (7초 클립)
- 오디오 볼륨: 정상 (mean: -25.8dB, max: -6.9dB)
- 비디오 해상도: 1080x1920 (쇼츠)

## 향후 개선 가능사항
1. 배경 블러 효과 옵션
2. 다양한 텍스트 애니메이션
3. 음성 속도 사용자 설정
4. 다국어 TTS 지원

## 자주 발생하는 문제와 해결법

### 1. 폰트가 적용되지 않는 경우
```bash
# 폰트 경로 확인
find /usr/share/fonts /home/$USER/.fonts -name "*NotoSans*" -type f | grep -i "bold"

# 폰트 권한 확인
ls -la /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
```

### 2. 정지 프레임 추출 실패
- **원인**: 비디오 파일 경로 오류, 시간 범위 초과
- **해결**: 
  ```python
  # 비디오 길이 확인
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
  ```

### 3. TTS 생성 실패
- **원인**: 네트워크 연결, Edge TTS 서버 문제
- **해결**: 
  ```python
  # 수동 테스트
  edge-tts --text "Hello" --voice en-US-AriaNeural --write-media test.mp3
  ```

### 4. 클립 병합 실패 (concat)
- **원인**: 코덱/파라미터 불일치
- **해결**: 모든 클립이 동일한 설정인지 확인
  ```bash
  # 클립 정보 확인
  for f in *.mp4; do echo "=== $f ==="; ffprobe -v error -show_streams $f | grep -E "(codec_name|width|height|pix_fmt)"; done
  ```

### 5. 텍스트 깨짐
- **원인**: 폰트가 한글을 지원하지 않음
- **해결**: NotoSans CJK 계열 폰트 사용 필수

## 디버깅 체크리스트

### 리뷰 클립이 제대로 생성되지 않을 때
1. [ ] video_path가 올바른가?
2. [ ] clip_timestamps가 비디오 길이 내에 있는가?
3. [ ] NotoSans Bold 폰트가 설치되어 있는가?
4. [ ] TTS가 정상 작동하는가?
5. [ ] FFmpeg가 최신 버전인가? (4.4+ 권장)

### 로그 확인 위치
```python
# review_clip_generator.py에서 추가된 로그
logger.info(f"Using NotoSans font: {path}")
logger.info(f"Extracting freeze frame at {freeze_time:.1f}s from {self.video_path}")
logger.info(f"Freeze frame extracted: {freeze_frame}")
```

## 핵심 설정값 정리

### 폰트 설정
- **경로**: `/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc`
- **테두리**: 5px (borderw=5)
- **색상**: 
  - 한글: #FFD700 (골드)
  - 영어: white (흰색)

### TTS 설정
- **음성**: en-US-AriaNeural
- **속도**: -10%
- **생성기**: `EdgeTTSGenerator(voice='en-US-AriaNeural', rate='-10%')`

### 자막 위치 (쇼츠)
```python
# 한글: 화면 하단에서 220px 위
kor_y_expr = "h-220"
# 영어: 화면 하단에서 360px 위  
eng_y_expr = "h-360"
```

### 크롭 필터 (쇼츠)
```python
crop_filter = "crop='min(iw,ih):min(iw,ih)',scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
```