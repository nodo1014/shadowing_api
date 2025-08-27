# ASS 자막 생성 가이드

## ⚠️ 중요: ASS 파일 생성은 반드시 아래 방법을 사용하세요

### 1. 기본 사용법 (권장)
```python
from ass_generator import ASSGenerator

generator = ASSGenerator()
generator.generate_ass(subtitles, output_path, is_shorts=False)
```

### 2. 여러 자막 파일 생성시
```python
from api.routes.extract import create_multi_subtitle_file

create_multi_subtitle_file(ass_path, subtitles, offset, is_shorts=False)
```

### 3. text_processing.py의 함수 사용시 (호환성 유지)
```python
from api.utils.text_processing import create_multi_subtitle_file
# 내부적으로 ASSGenerator를 사용합니다
```

## ❌ 사용하지 마세요 (DEPRECATED)

1. **직접 ASS 헤더 작성 금지**
   ```python
   # 잘못된 예
   ass_content = """[Script Info]
   Title: ...
   """
   ```

2. **mixed.py의 create_multi_subtitle_file 삭제됨**
   - 대신 extract.py의 함수를 import하여 사용

3. **하드코딩된 스타일 사용 금지**
   - 모든 스타일은 styles.py에서 관리

## 📁 파일 구조

- `ass_generator.py` - **핵심 ASS 생성 클래스**
- `styles.py` - **모든 스타일 설정 (폰트, 크기, 색상, 위치)**
- `api/routes/extract.py` - create_multi_subtitle_file 함수
- `api/utils/text_processing.py` - 래퍼 함수 (내부적으로 ASSGenerator 사용)

## 🔧 필수 ASS 헤더 설정

모든 ASS 파일에는 다음이 포함되어야 합니다:
```
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
```

이 설정이 없으면 폰트가 매우 크게 보입니다!

## 📝 변경 이력
- 2025-08-28: 모든 ASS 생성을 ASSGenerator로 통합
- mixed.py의 중복 함수 제거
- text_processing.py를 ASSGenerator 래퍼로 변경