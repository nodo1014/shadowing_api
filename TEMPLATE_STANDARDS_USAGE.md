# Template Standards 사용 가이드

## 개요
`template_standards.py`는 템플릿 시스템에서 발생하는 오디오/비디오 호환성 문제를 해결하기 위한 표준화 모듈입니다.

## 주요 문제점 해결
1. **무음 처리**: 44.1kHz 스테레오 WAV로 표준화
2. **프리즈 프레임**: 검은 배경 + 무음 WAV 결합
3. **병합**: 48kHz 스테레오로 재인코딩

## 사용 방법

### 1. Import
```python
from template_standards import TS
```

### 2. 프리즈 프레임 생성 교체

**기존 코드 (_create_freeze_frame_clip):**
```python
# 복잡한 FFmpeg 명령어 직접 구성
# 무음 WAV 수동 생성
# 오디오 포맷 문제 가능성
```

**새 코드:**
```python
freeze_path = TS.create_freeze_frame(
    video_path=video_path,
    frame_time=segment['end_time'] - 0.1,
    duration=0.5,
    output_path=freeze_path  # Optional
)
```

### 3. 클립 병합 교체

**기존 코드 (_merge_clips):**
```python
# -c copy 사용 시 호환성 문제
# 재인코딩 시 수동 설정
```

**새 코드:**
```python
success = TS.merge_clips(
    clips=all_clips,
    output_path=output_path,
    mode='reencode'  # 안전한 재인코딩
)
```

### 4. 검은 화면 갭 생성

**새 기능:**
```python
gap = TS.create_black_gap(duration=1.0)
clips.append(gap)
```

## 적용 예시

### Template 91에서 사용하는 경우:

```python
# _create_template1_clips 메서드 내부
for i, (mode, subtitle_type) in enumerate(modes):
    # 일반 클립 생성
    clip_path = f"/tmp/bookmark_{bookmark_index}_mode_{i}_{int(time.time() * 1000)}.mp4"
    
    # ... 클립 생성 코드 ...
    
    # 프리즈 프레임 생성 (기존 _create_freeze_frame_clip 대신)
    freeze_path = f"/tmp/bookmark_{bookmark_index}_freeze_{i}_{int(time.time() * 1000)}.mp4"
    freeze_time = segment['end_time'] - 0.1
    
    # TS 모듈 사용
    try:
        TS.create_freeze_frame(video_path, freeze_time, 0.5, freeze_path)
        clips.append(freeze_path)
        logger.info(f"✓ Created freeze frame: {os.path.basename(freeze_path)}")
    except Exception as e:
        logger.error(f"✗ Failed to create freeze frame: {e}")
```

### 병합 시:

```python
# _merge_clips 메서드 대체
def _merge_clips(self, clips: List[str], output_path: str) -> bool:
    """TS 모듈을 사용한 안전한 병합"""
    return TS.merge_clips(clips, output_path, mode='reencode')
```

## 장점

1. **일관성**: 모든 템플릿이 동일한 오디오/비디오 설정 사용
2. **안정성**: 검증된 FFmpeg 명령어 사용
3. **간편함**: 복잡한 설정 숨김
4. **디버깅**: 명확한 에러 메시지

## 주의사항

- 재인코딩 모드는 처리 시간이 더 걸리지만 안전합니다
- 기존 코드와 병행 사용 가능 (점진적 마이그레이션)
- 테스트 후 적용 권장

## 테스트 방법

1. 기존 템플릿 하나 선택
2. 프리즈 프레임 생성 부분만 먼저 교체
3. 정상 작동 확인 후 병합 부분 교체
4. 전체 테스트 후 다른 템플릿에 적용