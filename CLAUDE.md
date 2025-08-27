# Claude Context for Shadowing Maker

## 프로젝트 개요
YouTube Shorts용 영어 학습 비디오 자동 생성 시스템. 템플릿 기반으로 다양한 형식의 shadowing 영상을 만듦.

## 최근 개선사항 (2024-08-26)

### 리뷰 클립 개선
- **NotoSans Bold 폰트 적용**: 가독성 향상
- **테두리 5px로 두껍게**: 모바일에서도 선명
- **Aria 음성 + 속도 -10%**: 학습하기 좋은 속도
- **원본 비디오 정지 프레임 배경**: 맥락 있는 학습

### 핵심 원칙
1. **간단한 해결책 우선**: 복잡하게 생각하지 말고 직접적인 방법 사용
2. **기존 코드 활용**: 새로 만들기보다 있는 것을 수정
3. **당연한 로직 구현**: 사용자 입장에서 자연스러운 방식

## 주요 파일 구조

### 핵심 엔진
- `template_video_encoder.py`: 템플릿 기반 비디오 인코더
- `review_clip_generator.py`: 스터디 클립 생성 (TTS + 정지 프레임)
- `subtitle_pipeline.py`: 효율적인 자막 변환 파이프라인
- `edge_tts_util.py`: Edge TTS 래퍼

### API
- `clipping_api.py`: FastAPI 기반 REST API
- `monitor_jobs.py`: 작업 상태 모니터링

### 템플릿 정의
- `templates/shadowing_patterns.json`: 템플릿 패턴 정의

## 템플릿 시스템

### 일반 템플릿 (1-10)
- 1920x1080 가로 형식
- 다양한 반복 패턴

### 쇼츠 템플릿 (11-13) 
- 1080x1920 세로 형식
- 정사각형 크롭 적용
- 하단 자막 배치 (h-220, h-360)

### 스터디 모드
- `preview`: 맨 앞에 미리보기
- `review`: 맨 뒤에 복습

## 기술 스택
- Python 3.10+
- FastAPI
- FFmpeg
- Edge TTS
- SQLite (작업 추적)

## 자막 스타일 (쇼츠)
- **영어**: 흰색, 60pt, 화면 하단 360px
- **한글**: 골드색(#FFD700), 54pt, 화면 하단 220px
- **테두리**: 5px 검은색

## 인코딩 표준
- 비디오: H.264, CRF 16, preset medium
- 오디오: AAC 192k
- 프레임레이트: 30fps

## 주의사항
1. 모든 클립은 동일한 인코딩 파라미터 사용 (concat 호환성)
2. 파일 기반 처리가 메모리 기반보다 안정적
3. NotoSans CJK Bold 폰트 필수

## 디버깅 팁
- Gunicorn 리로드 문제 시 서버 재시작
- concat 실패 시 코덱/파라미터 확인
- TTS 실패 시 네트워크 연결 확인

## 향후 과제
- 배경 효과 다양화
- 텍스트 애니메이션
- 사용자 설정 확장