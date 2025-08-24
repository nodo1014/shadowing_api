# 자막 생성 시스템 최적화 가이드

## 개선 사항

### 1. 새로운 SubtitlePipeline 도입
- **파일**: `subtitle_pipeline.py`
- **주요 기능**:
  - 인메모리 자막 생성
  - 자막 변형 캐싱
  - 통합된 자막 처리 로직
  - 중복 제거

### 2. 성능 개선 포인트

#### 이전 방식의 문제점:
```python
# 각 클립마다 파일 I/O 발생
for clip in clips:
    create_ass_file()  # 파일 쓰기
    encode_video()     # 파일 읽기
    delete_ass_file()  # 파일 삭제
```

#### 새로운 방식:
```python
# 파이프라인으로 메모리에서 처리
pipeline = SubtitlePipeline(subtitle_data)
content = pipeline.generate_ass_content(variant_type)  # 메모리에서 생성
# 필요할 때만 파일로 저장
```

### 3. 주요 개선 클래스

#### SubtitlePipeline
```python
class SubtitlePipeline:
    """효율적인 자막 처리 파이프라인"""
    
    def __init__(self, base_subtitle_data: Dict):
        self._variants = {}  # 캐싱
        self._blank_text_cache = {}  # 블랭크 텍스트 캐싱
    
    def get_variant(self, variant_type: SubtitleType) -> SubtitleVariant:
        """캐싱된 자막 변형 반환"""
        
    def generate_ass_content(self, variant_type: SubtitleType) -> str:
        """메모리에서 ASS 콘텐츠 생성"""
```

#### OptimizedBatchProcessor
```python
class OptimizedBatchProcessor:
    """배치 처리 최적화"""
    
    async def process_batch(...):
        # 1. 모든 자막 사전 준비
        # 2. 병렬 처리
        # 3. 캐싱 활용
```

### 4. 사용 방법

#### 기존 코드 마이그레이션:
```python
# 이전 방식
from subtitle_generator import SubtitleGenerator
generator = SubtitleGenerator()
generator.generate_full_subtitle(data, 'output.ass')

# 새로운 방식
from subtitle_pipeline import SubtitlePipeline, SubtitleType
pipeline = SubtitlePipeline(data)
pipeline.save_variant_to_file(SubtitleType.FULL, 'output.ass')
```

### 5. 성능 비교

| 항목 | 이전 | 개선 후 |
|------|------|---------|
| 파일 I/O | 클립당 3-4회 | 필요시만 |
| 메모리 사용 | 낮음 | 중간 (캐싱) |
| 처리 속도 | 순차적 | 병렬 가능 |
| 중복 처리 | 있음 | 캐싱으로 제거 |

### 6. 추가 최적화 옵션

1. **Redis 캐싱**: 서버 재시작 후에도 캐시 유지
2. **FFmpeg 파이프**: 파일 없이 직접 스트리밍
3. **사전 컴파일**: 자주 사용하는 패턴 미리 준비

### 7. 주의사항

- 메모리 사용량 모니터링 필요
- 대용량 배치 처리 시 캐시 크기 제한 고려
- 기존 코드와의 호환성 유지

### 8. 향후 개선 방향

1. WebAssembly로 클라이언트 사이드 자막 생성
2. 분산 처리 시스템 구축
3. AI 기반 자막 최적화