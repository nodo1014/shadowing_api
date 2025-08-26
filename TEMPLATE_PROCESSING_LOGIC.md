# 템플릿 처리 로직 문서

## 개요
이 문서는 shadowing_maker_xls의 템플릿 처리 시스템에 대한 전체적인 구조와 로직을 설명합니다.

## 템플릿 종류

### 1. 일반 템플릿 (template_1 ~ template_90)
- **구조**: `clips` 기반
- **처리 메서드**: `create_from_template()`
- **특징**: 
  - 각 클립에 대해 정의된 자막 모드와 반복 횟수를 가짐
  - 개별 클립을 생성하고 연결하는 방식

### 2. 특수 템플릿 (template_91 ~ template_93)
- **구조**: `patterns` 기반
- **처리 메서드**: `apply_template()`
- **특징**:
  - 연속 재생 모드 (`continuous_with_bookmarks`)
  - 프리즈 프레임, 북마크 처리 등 특수 기능 포함

## 템플릿 JSON 구조

### 일반 템플릿 구조 예시 (template_1)
```json
{
  "name": "Progressive Learning",
  "description": "무자막 1회, 블랭크 1회, 블랭크+한글 1회, 영한자막 1회, 무자막 1회",
  "clips": [
    {
      "subtitle_mode": "no_subtitle",
      "folder_name": "1_nosub",
      "count": 1,
      "subtitle_type": null
    },
    {
      "subtitle_mode": "blank_subtitle",
      "folder_name": "2_blank",
      "count": 1,
      "subtitle_type": "blank"
    }
    // ... 추가 클립들
  ],
  "gap_duration": 0.5
}
```

### 특수 템플릿 구조 예시 (template_91)
```json
{
  "name": "Continuous Play with Bookmark Focus",
  "description": "연속 재생 중 북마크 구간만 템플릿1 반복",
  "mode": "continuous_with_bookmarks",
  "default_subtitle": "full",
  "bookmark_template": "template_1",
  "requires_multiple_bookmarks": false,
  "patterns": [
    {
      "type": "freeze_frame",
      "duration": 0.5,
      "position": "start"
    },
    {
      "type": "normal_play",
      "subtitle": "full"
    },
    {
      "type": "freeze_frame",
      "duration": 0.5,
      "position": "end"
    }
  ],
  "segment_duration": 3.0,
  "subtitle_style": {
    "font_size": 24,
    "outline_width": 2,
    "margin_bottom": 60
  }
}
```

## 처리 흐름

### 1. API 요청 처리 (clipping_api.py)

```python
# Template 91 특별 처리
if request.template_number == 91:
    return await _process_template_91_single_clip(job_id, request)

# 일반 템플릿 처리
if request.template_number in [91, 92, 93]:
    # apply_template 사용
    success = template_encoder.apply_template(...)
else:
    # create_from_template 사용
    success = template_encoder.create_from_template(...)
```

### 2. 템플릿 검증 (validate_template)

```python
def validate_template(self, template: Dict) -> bool:
    # 특수 템플릿 검증
    if template.get('mode') == 'continuous_with_bookmarks':
        required_fields = ['patterns', 'segment_duration', 'subtitle_style']
        # 필드 검증 로직
        return True
    
    # 일반 템플릿 검증
    if 'clips' not in template:
        return False
    
    return True
```

### 3. 템플릿 적용 (apply_template)

```python
def apply_template(self, video_path: str, output_path: str, 
                  template_name: str, segments: List[Dict]) -> bool:
    # 템플릿 로드
    template = self.get_template(template_name)
    
    # 템플릿 검증
    if not self.validate_template(template):
        return False
    
    # template_91 특별 처리
    if template_name == 'template_91' and template.get('mode') == 'continuous_with_bookmarks':
        return self._apply_continuous_template(...)
    
    # 일반 템플릿 처리
    if 'clips' in template:
        return self._apply_clips_template(...)
```

## 주요 메서드 설명

### create_from_template()
- **용도**: 일반 템플릿(clips 구조) 처리
- **입력**: 템플릿명, 미디어 경로, 자막 데이터, 시작/종료 시간
- **처리**: 
  1. 템플릿의 clips 구조에 따라 개별 클립 생성
  2. 각 클립에 정의된 자막 타입 적용
  3. 모든 클립을 연결하여 최종 비디오 생성

### apply_template()
- **용도**: 특수 템플릿(patterns 구조) 처리
- **입력**: 비디오 경로, 출력 경로, 템플릿명, 세그먼트 리스트
- **처리**:
  1. 템플릿 타입에 따라 적절한 처리 메서드 호출
  2. continuous_with_bookmarks 모드는 _apply_continuous_template() 호출
  3. clips 구조는 _apply_clips_template() 호출

### _apply_clips_template()
- **용도**: clips 구조를 가진 템플릿 처리
- **처리**: 각 세그먼트에 대해 템플릿의 clips 설정 적용

### _apply_continuous_template()
- **용도**: continuous_with_bookmarks 모드 처리
- **처리**: 
  1. 북마크된 세그먼트와 일반 세그먼트 분리
  2. 각 세그먼트에 patterns 적용
  3. 프리즈 프레임, 자막 처리 등 특수 효과 적용

## 쇼츠 템플릿 처리

### _encode_clip() 메서드
```python
# 현재 템플릿이 쇼츠인지 확인
current_template = getattr(self, '_current_template_name', '')
is_shorts = current_template and '_shorts' in current_template

if is_shorts:
    # 쇼츠용 크롭 적용 (1080x1920)
    return self._encode_clip_with_crop(...)
```

## 자막 처리

### 자막 타입
1. **no_subtitle**: 자막 없음
2. **blank**: 영어 자막만 블랭크 처리
3. **blank_korean**: 영어 블랭크 + 한글 자막
4. **full**: 영어 + 한글 자막 모두 표시
5. **english_only**: 영어 자막만
6. **korean_only**: 한글 자막만

### _create_template_subtitle() 메서드
- 세그먼트 데이터와 자막 타입에 따라 적절한 자막 파일 생성
- 블랭크 처리, 키워드 강조 등 특수 효과 적용

## 오류 처리 및 검증

### 주요 검증 포인트
1. **템플릿 존재 여부**: get_template()에서 확인
2. **템플릿 구조 검증**: validate_template()에서 처리
3. **None 체크**: current_template이 None일 때 처리
4. **파일 경로 검증**: 미디어 파일 존재 여부 확인

### 에러 핸들링
```python
try:
    # 템플릿 처리 로직
except Exception as e:
    logger.error(f"Error applying template: {e}", exc_info=True)
    return False
```

## 최근 수정 사항

### 1. TypeError 수정 (2025-08-25)
- 문제: `'_shorts' in current_template`에서 current_template이 None일 때 오류
- 해결: `current_template and '_shorts' in current_template`로 수정

### 2. validate_template 개선
- template_91의 필수 필드 검증 추가
- 일반 템플릿과 특수 템플릿 구분 로직 명확화

### 3. template_91 JSON 구조 보완
- patterns, segment_duration, subtitle_style 필드 추가
- continuous_with_bookmarks 모드 정상 작동 보장

## 템플릿 91과 일반 템플릿의 핵심 차이점

### 1. 처리 방식의 차이
- **일반 템플릿 (1-90)**:
  - 개별 클립 생성 → concat으로 연결
  - 각 클립은 독립적으로 인코딩됨
  - 클립 간 전환이 명확함
  
- **템플릿 91**:
  - 전체 비디오를 연속 재생하면서 처리
  - 북마크 구간만 특별 처리 (템플릿 1 적용)
  - 프리즈프레임과 자막을 실시간으로 적용

### 2. 프리즈프레임 처리의 중요성 ⚠️ 

**이것은 가장 자주 발생하는 문제이며, 반드시 이해해야 하는 핵심 사항입니다.**

#### 문제점 상세 분석
프리즈프레임 생성 시 가장 자주 발생하는 문제:

1. **무음 구간 생성 문제**
   - 증상: 프리즈프레임 구간에서 오디오가 완전히 사라짐
   - 원인: 이미지 루프로만 비디오를 생성하면 오디오 트랙이 없음
   - 결과: 플레이어가 오디오 싱크를 잃어버려 이후 재생이 틀어짐

2. **대기 시간 발생 (가장 심각한 문제)**
   - 증상: 프리즈프레임 후 1-2초간 화면이 멈춤
   - 원인: PTS(Presentation Timestamp) 불일치로 플레이어가 다음 프레임을 기다림
   - 결과: 사용자 경험 저하, 끊김 현상

3. **재생 끊김 현상**
   - 증상: concat 시 프레임 전환 부분에서 깜빡임 또는 멈춤
   - 원인: 서로 다른 인코딩 파라미터로 생성된 세그먼트 연결
   - 결과: 전문적이지 못한 비디오 품질

#### 실제 사례 - 문제 발생 시나리오
```bash
# ❌ 실패 사례: 이렇게 하면 반드시 문제가 발생합니다
# 1. 프리즈프레임 생성 (오디오 없음)
ffmpeg -loop 1 -i frame.png -t 0.5 -c:v libx264 freeze.mp4

# 2. 원본 클립
ffmpeg -i input.mp4 -ss 10 -t 5 clip.mp4

# 3. concat으로 연결
ffmpeg -f concat -i list.txt -c copy output.mp4
# 결과: 프리즈프레임에서 무음 → 클립 재생 시 오디오 싱크 깨짐 → 대기 발생
```

#### 해결 방법 - 재인코딩 필수 ⭐
```python
def _create_freeze_frame_with_audio(self, frame_path: str, duration: float, 
                                   audio_path: str, output_path: str) -> bool:
    """프리즈프레임 생성 시 오디오 포함하여 재인코딩"""
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-i', frame_path,
        '-i', audio_path,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-shortest',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
```

### 3. 핵심 기술적 차이

#### 일반 템플릿 - concat 방식
```bash
# 개별 클립 생성
ffmpeg -i input.mp4 -ss 0 -t 2 clip1.mp4
ffmpeg -i input.mp4 -ss 0 -t 2 clip2.mp4

# concat으로 연결
ffmpeg -f concat -i list.txt -c copy output.mp4
```

#### 템플릿 91 - 재인코딩 방식
```bash
# 전체를 한 번에 처리하며 필터 적용
ffmpeg -i input.mp4 \
  -filter_complex "[0:v]freezeframe=...[freeze];[freeze][0:a]..." \
  -c:v libx264 -c:a aac output.mp4
```

### 4. 프리즈프레임 모범 사례

#### ❌ 잘못된 방법
```python
# 비디오만 처리하고 오디오 무시
cmd = ['ffmpeg', '-loop', '1', '-i', 'frame.png', '-t', '0.5', 'freeze.mp4']
```

#### ✅ 올바른 방법
```python
# 오디오 트랙 유지하며 재인코딩
cmd = [
    'ffmpeg', '-y',
    '-i', original_video,  # 원본 비디오 (오디오 소스)
    '-loop', '1', '-i', frame_image,  # 프리즈할 프레임
    '-filter_complex', '[1:v]scale=1920:1080[v]',  # 비디오 처리
    '-map', '[v]', '-map', '0:a',  # 비디오는 프레임, 오디오는 원본
    '-t', duration,
    '-c:v', 'libx264', '-c:a', 'aac',  # 재인코딩 필수
    output
]
```

### 5. 왜 재인코딩이 필요한가? (핵심 원리)

1. **타임스탬프 정렬**: 
   - 모든 프레임의 PTS/DTS가 올바르게 정렬됨
   - concat은 타임스탬프를 재계산하지 않아 문제 발생

2. **오디오 연속성**: 
   - 오디오 스트림이 끊기지 않고 연속됨
   - 프리즈프레임에도 원본 오디오가 계속 재생됨

3. **코덱 일관성**: 
   - 모든 세그먼트가 동일한 코덱 파라미터 사용
   - 키프레임 간격, 비트레이트 등이 일관됨

4. **플레이어 호환성**: 
   - 모든 플레이어에서 문제없이 재생
   - 스트리밍 서비스에서도 안정적으로 작동

### 6. 실전 디버깅 가이드

#### 프리즈프레임 문제 진단 체크리스트
- [ ] 프리즈프레임에 오디오 트랙이 있는가?
- [ ] 모든 세그먼트의 FPS가 동일한가?
- [ ] 코덱 파라미터가 일치하는가?
- [ ] PTS가 연속적인가?

#### 문제 확인 명령어
```bash
# 세그먼트 정보 확인
ffprobe -v error -show_streams freeze.mp4
# 오디오 트랙이 있는지 확인

# PTS 확인
ffprobe -show_packets -select_streams v:0 output.mp4 | grep pts_time
# 시간이 연속적인지 확인
```

### 7. 성능 vs 품질 트레이드오프

- **concat (일반 템플릿)**: 
  - 장점: 빠른 처리, 낮은 CPU 사용
  - 단점: 프리즈프레임 처리 시 문제 발생 가능
  - 적합한 경우: 단순 클립 연결, 프리즈프레임 없음

- **재인코딩 (템플릿 91)**:
  - 장점: 안정적인 품질, 모든 효과 적용 가능
  - 단점: 처리 시간 증가, CPU 사용량 높음
  - 적합한 경우: 프리즈프레임 필요, 복잡한 효과 적용

### 8. 템플릿 91의 핵심 구현 원리

```python
def _apply_continuous_template(self, video_path, output_path, template, segments):
    """연속 재생 + 북마크 구간 특별 처리"""
    
    # 1. 북마크 구간 식별
    bookmarked_segments = [s for s in segments if s.get('is_bookmarked')]
    
    # 2. 각 세그먼트에 대해 패턴 적용
    for segment in segments:
        if segment.get('is_bookmarked'):
            # 북마크 구간: 프리즈프레임 + 템플릿1 적용
            patterns = [
                {"type": "freeze_frame", "duration": 0.5, "position": "start"},
                {"type": "apply_template", "template": "template_1"},
                {"type": "freeze_frame", "duration": 0.5, "position": "end"}
            ]
        else:
            # 일반 구간: 그대로 재생
            patterns = [{"type": "normal_play", "subtitle": "full"}]
    
    # 3. 전체를 하나의 비디오로 재인코딩
    # 이 과정에서 모든 프리즈프레임에 오디오가 유지됨
```

### 9. 중요 교훈 정리 📌

1. **프리즈프레임은 반드시 오디오와 함께 생성**
2. **concat 대신 재인코딩을 선택해야 하는 경우를 명확히 인지**
3. **타임스탬프 연속성은 비디오 품질의 핵심**
4. **테스트 시 반드시 전체 재생으로 확인 (부분 재생만으로는 문제 발견 어려움)**

## 향후 개선 사항

1. **템플릿 상속 구조**: 공통 기능을 base template에서 상속받는 구조 고려
2. **동적 템플릿 로딩**: 런타임에 새로운 템플릿 추가 가능하도록 개선
3. **템플릿 프리뷰**: 템플릿 적용 전 미리보기 기능
4. **성능 최적화**: 대용량 비디오 처리 시 메모리 사용량 최적화
5. **프리즈프레임 캐싱**: 자주 사용되는 프리즈프레임 캐싱으로 성능 향상