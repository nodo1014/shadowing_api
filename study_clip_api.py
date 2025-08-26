"""
Study Clip API - 독립적인 스터디 클립 생성 엔드포인트
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
import uuid
import logging
from pathlib import Path
from datetime import datetime
from review_clip_generator import ReviewClipGenerator

router = APIRouter(prefix="/api/study", tags=["Study Clips"])
logger = logging.getLogger(__name__)

# 작업 상태 저장 (간단한 메모리 저장소)
study_jobs = {}


class StudyClipData(BaseModel):
    """개별 클립 데이터"""
    text_eng: str = Field(..., description="영어 텍스트")
    text_kor: str = Field(..., description="한글 텍스트")
    start_time: float = Field(..., description="시작 시간")
    end_time: float = Field(..., description="종료 시간")


class StudyClipRequest(BaseModel):
    """스터디 클립 생성 요청"""
    video_path: str = Field(..., description="원본 비디오 경로")
    clips: List[StudyClipData] = Field(..., description="클립 데이터 리스트")
    title: str = Field("스피드 복습", description="타이틀 텍스트")
    mode: str = Field("review", description="모드: preview(미리보기) 또는 review(복습)")
    is_shorts: bool = Field(True, description="쇼츠 형식 여부")
    
    # TTS 옵션
    voice: str = Field("en-US-AriaNeural", description="TTS 음성")
    rate: str = Field("-10%", description="TTS 속도")
    
    # 스타일 옵션
    font_size_kor: int = Field(54, description="한글 폰트 크기")
    font_size_eng: int = Field(60, description="영어 폰트 크기")
    border_width: int = Field(5, description="텍스트 테두리 두께")


class StudyClipResponse(BaseModel):
    """스터디 클립 생성 응답"""
    job_id: str
    status: str = "processing"
    message: str = "스터디 클립 생성 중..."


class StudyJobStatus(BaseModel):
    """작업 상태"""
    job_id: str
    status: str
    progress: int = 0
    message: str
    output_file: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


@router.post("/create", response_model=StudyClipResponse)
async def create_study_clip(
    request: StudyClipRequest,
    background_tasks: BackgroundTasks
):
    """
    스터디 클립을 생성합니다.
    
    - 원본 비디오에서 정지 프레임 추출
    - TTS로 오디오 생성
    - NotoSans Bold 폰트로 텍스트 렌더링
    - 쇼츠 형식 지원
    """
    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # 작업 상태 초기화
    study_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "message": "스터디 클립 생성 시작...",
        "output_file": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }
    
    # 백그라운드 작업 추가
    background_tasks.add_task(
        process_study_clip,
        job_id,
        request
    )
    
    return StudyClipResponse(
        job_id=job_id,
        status="processing",
        message="스터디 클립 생성이 시작되었습니다."
    )


async def process_study_clip(job_id: str, request: StudyClipRequest):
    """백그라운드에서 스터디 클립 처리"""
    try:
        # 출력 디렉토리 생성
        output_dir = Path("output/study_clips") / datetime.now().strftime("%Y-%m-%d")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 출력 파일명
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_text = "preview" if request.mode == "preview" else "review"
        output_filename = f"{timestamp}_study_{mode_text}_{job_id[:8]}.mp4"
        output_path = output_dir / output_filename
        
        # 진행 상태 업데이트
        study_jobs[job_id]["message"] = "TTS 생성 중..."
        study_jobs[job_id]["progress"] = 20
        
        # ReviewClipGenerator 사용 (설정 커스터마이징)
        generator = ReviewClipGenerator()
        
        # 클립 데이터 준비
        clips_data = []
        clip_timestamps = []
        
        for clip in request.clips:
            clips_data.append({
                'text_eng': clip.text_eng,
                'text_kor': clip.text_kor
            })
            clip_timestamps.append((clip.start_time, clip.end_time))
        
        # 진행 상태 업데이트
        study_jobs[job_id]["message"] = "비디오 생성 중..."
        study_jobs[job_id]["progress"] = 50
        
        # 템플릿 번호 (쇼츠 여부에 따라)
        template_number = 11 if request.is_shorts else 1
        
        # 타이틀 텍스트
        title = request.title
        if request.mode == "preview":
            title = title.replace("복습", "미리보기")
        
        # 스터디 클립 생성
        success = await generator.create_review_clip(
            clips_data=clips_data,
            output_path=str(output_path),
            title=title,
            template_number=template_number,
            video_path=request.video_path,
            clip_timestamps=clip_timestamps
        )
        
        if success and output_path.exists():
            # 성공
            study_jobs[job_id]["status"] = "completed"
            study_jobs[job_id]["progress"] = 100
            study_jobs[job_id]["message"] = "스터디 클립 생성 완료!"
            study_jobs[job_id]["output_file"] = str(output_path)
            study_jobs[job_id]["completed_at"] = datetime.now().isoformat()
            
            logger.info(f"Study clip created successfully: {output_path}")
        else:
            raise Exception("스터디 클립 생성 실패")
            
    except Exception as e:
        # 실패
        study_jobs[job_id]["status"] = "failed"
        study_jobs[job_id]["error"] = str(e)
        study_jobs[job_id]["message"] = f"오류 발생: {str(e)}"
        logger.error(f"Study clip generation failed: {e}", exc_info=True)


@router.get("/status/{job_id}", response_model=StudyJobStatus)
async def get_study_job_status(job_id: str):
    """스터디 클립 생성 작업 상태를 확인합니다."""
    if job_id not in study_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return StudyJobStatus(
        job_id=job_id,
        **study_jobs[job_id]
    )


@router.get("/download/{job_id}")
async def download_study_clip(job_id: str):
    """생성된 스터디 클립을 다운로드합니다."""
    if job_id not in study_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = study_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    output_file = job["output_file"]
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        output_file,
        media_type="video/mp4",
        filename=f"study_clip_{job_id[:8]}.mp4"
    )


@router.post("/test")
async def test_study_clip_generation():
    """
    테스트용 엔드포인트 - 샘플 데이터로 스터디 클립 생성
    """
    test_request = StudyClipRequest(
        video_path="/mnt/qnap/media_eng/indexed_media/Animation/KPop.Demon.Hunters.2025.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4",
        clips=[
            StudyClipData(
                text_eng="You will be Hunters.",
                text_kor="너희는 헌터가 될 거야.",
                start_time=50.0,
                end_time=52.5
            ),
            StudyClipData(
                text_eng="The world needs heroes.",
                text_kor="세상은 영웅이 필요해.",
                start_time=53.0,
                end_time=56.0
            )
        ],
        title="스피드 복습",
        mode="review",
        is_shorts=True
    )
    
    # 실제 생성은 하지 않고 요청 형식만 반환
    return {
        "message": "테스트 요청 형식입니다. POST /api/study/create 로 실제 요청을 보내세요.",
        "sample_request": test_request.dict()
    }


# 별도 실행을 위한 코드
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="Study Clip API", version="1.0.0")
    app.include_router(router)
    
    @app.get("/")
    async def root():
        return {"message": "Study Clip API", "docs": "/docs"}
    
    uvicorn.run(app, host="0.0.0.0", port=8001)