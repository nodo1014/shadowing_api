# 배치 처리 안정성 개선 방안

## 발견된 문제점

1. **메모리 누수**
   - FFmpeg 프로세스가 제대로 종료되지 않음
   - 임시 파일이 계속 쌓임
   - 대용량 stderr/stdout 버퍼로 인한 메모리 사용

2. **동시 실행 제한 없음**
   - 모든 클립을 순차 처리하여 하나라도 실패하면 전체 중단
   - FFmpeg 프로세스가 무제한으로 생성 가능

3. **타임아웃 문제**
   - 고정된 300초 타임아웃으로 긴 비디오 처리 불가
   - 프로세스 그룹 관리 미흡으로 좀비 프로세스 발생

## 적용된 개선사항

### 1. 로깅 시스템 개선
- print문을 logger로 교체
- 상세한 에러 추적 가능

### 2. 프로세스 관리 개선 (video_encoder.py)
```python
# 프로세스 그룹 사용으로 자식 프로세스도 함께 종료
preexec_fn=os.setsid if os.name != 'nt' else None

# 타임아웃시 전체 프로세스 그룹 종료
os.killpg(os.getpgid(process.pid), signal.SIGTERM)
```

### 3. 배치 처리 최적화 (batch_improvements.py)
- 동시 실행 제한 (Semaphore 사용)
- 리소스 체크 (메모리, 디스크)
- 동적 타임아웃 계산
- 임시 파일 자동 정리

## 즉시 적용 가능한 해결책

### 1. 배치 요청시 클립 수 제한
```python
# clipping_api.py에 추가
MAX_CLIPS_PER_BATCH = 10

if len(request.clips) > MAX_CLIPS_PER_BATCH:
    raise HTTPException(400, f"Too many clips. Maximum {MAX_CLIPS_PER_BATCH} clips per batch")
```

### 2. 메모리 모니터링 추가
```python
# 배치 처리 전 메모리 체크
import psutil
if psutil.virtual_memory().percent > 80:
    raise HTTPException(503, "Server busy. Please try again later")
```

### 3. 비동기 처리로 전환
- 현재 순차 처리를 병렬 처리로 변경
- 실패한 클립이 있어도 나머지는 계속 처리

## 권장사항

1. **Redis Queue 사용**
   - 긴 작업을 별도 워커로 분리
   - Celery나 RQ 같은 작업 큐 도입

2. **스트리밍 처리**
   - 전체 비디오를 메모리에 로드하지 않고 스트리밍 처리

3. **프로그레시브 다운로드**
   - 완성된 클립부터 즉시 다운로드 가능하도록

4. **자동 재시작**
   - systemd 서비스로 등록하여 크래시시 자동 재시작

## 테스트 방법

1. 작은 배치로 시작 (2-3개 클립)
2. 리소스 모니터링하며 점진적 증가
3. 로그 파일 확인으로 에러 패턴 분석