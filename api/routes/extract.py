"""
Extract Range Routes - 구간 추출 (원본 스타일)
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from typing import List, Optional
import uuid
import logging
import json
import time
from datetime import datetime
from pathlib import Path

from api.models import ExtractRangeRequest, SubtitleInfo, ClippingResponse
from api.models.validators import MediaValidator
from api.config import OUTPUT_DIR, executor, TEMPLATE_MAPPING
from api.utils import update_job_status_both, job_status
from api.utils.id_generator import get_next_folder_id
from api.db_utils import (
    create_job_in_db,
    create_media_source,
    create_subtitle_record,
    create_output_video,
    update_job_status_db,
    add_processing_log,
    log_api_request,
    get_client_info,
    ensure_templates_populated
)

# Import required modules from parent directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from template_video_encoder import TemplateVideoEncoder
from ass_generator import ASSGenerator
from database_v2.models_v2 import DatabaseManager, APIRequest

router = APIRouter(prefix="/api", tags=["Extract"])
logger = logging.getLogger(__name__)


@router.post("/extract/range",
             response_model=ClippingResponse,
             summary="구간 추출 (원본 스타일)")
async def extract_range(
    request: ExtractRangeRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    지정된 구간을 추출하여 여러 자막을 포함한 하나의 클립을 생성합니다.
    
    - 문장 단위 분할 없음
    - 자막은 원본 타이밍에 렌더링
    - 스타일은 통일된 형식 적용
    """
    # Job ID는 여전히 UUID 사용 (DB 키로 사용)
    job_id = str(uuid.uuid4())
    
    # 폴더명은 날짜별 순차 번호 사용
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder_id = get_next_folder_id(date_str)
    
    # 요청 시작 시간
    request_start_time = time.time()
    
    # Debug logging
    logger.info(f"[Job {job_id}] Range extraction request")
    
    # 클라이언트 정보 추출
    client_info = get_client_info(req)
    logger.info(f"  Range: {request.start_time}-{request.end_time}s")
    logger.info(f"  Subtitles: {len(request.subtitles)} items")
    logger.info(f"  Template: {request.template_number}")
    
    # 작업 상태 초기화
    job_data = {
        "status": "pending",
        "progress": 0,
        "message": "구간 추출 대기 중...",
        "output_file": None,
        "error": None,
        "media_path": request.media_path,
        "template_number": request.template_number,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "subtitle_count": len(request.subtitles),
        "folder_id": folder_id  # 순차 폴더 ID 추가
    }
    job_status[job_id] = job_data
    
    # 새로운 DB에 저장
    try:
        with DatabaseManager.get_session() as session:
            # 템플릿 확인
            ensure_templates_populated(session)
            
            # Job 생성
            job = create_job_in_db(
                session=session,
                job_id=job_id,
                job_type="range_extraction",
                api_endpoint="/api/extract/range",
                request_data=request.dict(),
                client_info=client_info,
                extra_data={"folder_id": folder_id}
            )
            
            # API 요청 로깅
            log_api_request(
                session=session,
                endpoint="/api/extract/range",
                method="POST",
                client_info=client_info,
                request_data=request.dict(),
                job_id=job_id
            )
    except Exception as e:
        logger.error(f"Failed to save job to new DB: {e}")
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_range_extraction,
        job_id,
        request
    )
    
    # API 응답 로깅
    response_time_ms = int((time.time() - request_start_time) * 1000)
    response = ClippingResponse(
        job_id=job_id,
        status="accepted",
        message=f"구간 추출 작업이 시작되었습니다. ({request.end_time - request.start_time:.1f}초)"
    )
    
    # API 응답 업데이트
    try:
        with DatabaseManager.get_session() as session:
            api_request = session.query(APIRequest).filter_by(job_id=job_id).first()
            if api_request:
                api_request.response_status = 200
                api_request.response_time_ms = response_time_ms
                api_request.response_body = json.dumps(response.dict())
                session.commit()
    except Exception as e:
        logger.error(f"Failed to update API response in DB: {e}")
    
    return response


async def process_range_extraction(job_id: str, request: ExtractRangeRequest):
    """구간 추출 처리"""
    try:
        # 작업 시작
        update_job_status_both(job_id, "processing", 10, message="구간 추출 준비 중...")
        
        # 새 DB에도 상태 업데이트
        with DatabaseManager.get_session() as session:
            update_job_status_db(session, job_id, "processing", 10, "구간 추출 준비 중...")
            add_processing_log(session, job_id, "info", "initialization", "구간 추출 작업 시작")
        
        # 미디어 경로 검증
        media_path = MediaValidator.validate_media_path(request.media_path)
        if not media_path:
            raise ValueError(f"Invalid media path: {request.media_path}")
        
        # 날짜별 디렉토리 구조
        date_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = OUTPUT_DIR / date_str
        daily_dir.mkdir(exist_ok=True)
        
        # job_status에서 folder_id 가져오기
        folder_id = job_status.get(job_id, {}).get('folder_id', job_id)
        job_dir = daily_dir / folder_id
        job_dir.mkdir(exist_ok=True)
        
        # 자막 파일 생성
        update_job_status_both(job_id, "processing", 20, message="자막 파일 생성 중...")
        
        ass_path = job_dir / "subtitles.ass"
        # template 10번대는 쇼츠용
        is_shorts = request.template_number >= 10
        create_multi_subtitle_file(ass_path, request.subtitles, request.start_time, is_shorts=is_shorts)
        
        # 새 DB에 미디어 소스 및 자막 정보 저장
        with DatabaseManager.get_session() as session:
            # 미디어 소스 저장
            create_media_source(
                session=session,
                job_id=job_id,
                file_path=str(media_path)
            )
            
            # 각 자막 정보 저장
            for idx, subtitle in enumerate(request.subtitles):
                create_subtitle_record(
                    session=session,
                    job_id=job_id,
                    text_eng=subtitle.eng,
                    text_kor=subtitle.kor,
                    start_time=subtitle.start,
                    end_time=subtitle.end
                )
            
            update_job_status_db(session, job_id, "processing", 20, "자막 파일 생성 중...")
            add_processing_log(session, job_id, "info", "subtitle", f"{len(request.subtitles)}개 자막 저장 완료")
        
        # 자막 데이터 준비 (템플릿 인코더용)
        # 전체 구간을 하나의 subtitle_data로 처리
        subtitle_data = {
            'start_time': 0,  # 클립 내에서는 0부터 시작
            'end_time': request.end_time - request.start_time,
            'subtitles': request.subtitles,  # 여러 자막 정보 전달
            'ass_file': str(ass_path),  # 생성된 ASS 파일 경로
            'template_number': request.template_number,
            'title_1': request.title_1,
            'title_2': request.title_2
        }
        
        # 비디오 추출
        update_job_status_both(job_id, "processing", 50, message="비디오 추출 중...")
        
        # 템플릿 기반 인코더 사용
        template_encoder = TemplateVideoEncoder()
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        duration = int(request.end_time - request.start_time)
        filename = f"{timestamp}_extract_{duration}s.mp4"
        output_path = job_dir / filename
        
        # 템플릿 이름
        template_name = TEMPLATE_MAPPING.get(request.template_number, "template_original")
        
        # 템플릿을 사용하여 비디오 생성
        success = template_encoder.create_from_template(
            template_name=template_name,
            media_path=str(media_path),
            subtitle_data=subtitle_data,
            output_path=str(output_path),
            start_time=request.start_time,
            end_time=request.end_time,
            padding_before=0.5,
            padding_after=0.5,
            save_individual_clips=False
        )
        
        if success and output_path.exists():
            update_job_status_both(job_id, "processing", 90, message="추출 완료, 파일 정리 중...")
            
            # 파일 크기 계산
            file_size = output_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # 메타데이터 저장
            metadata = {
                "job_id": job_id,
                "media_path": str(media_path),
                "template_number": request.template_number,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "duration": request.end_time - request.start_time,
                "subtitle_count": len(request.subtitles),
                "subtitles": [s.dict() for s in request.subtitles],
                "output_file": str(output_path),
                "file_size_mb": file_size_mb,
                "created_at": datetime.now().isoformat()
            }
            
            with open(job_dir / "extraction_metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 새 DB에 출력 비디오 정보 저장
            with DatabaseManager.get_session() as session:
                create_output_video(
                    session=session,
                    job_id=job_id,
                    video_type="extracted",
                    file_path=str(output_path),
                    subtitle_mode="both"  # 추출은 보통 모든 자막 포함
                )
                
                update_job_status_db(session, job_id, "processing", 90, "추출 완료, 파일 정리 중...")
                add_processing_log(session, job_id, "info", "extraction", "구간 추출 완료")
            
            # 작업 완료
            update_job_status_both(
                job_id,
                "completed",
                100,
                message="구간 추출이 완료되었습니다.",
                output_file=str(output_path)
            )
            
            # 새 DB에도 완료 상태 업데이트
            with DatabaseManager.get_session() as session:
                update_job_status_db(session, job_id, "completed", 100, "구간 추출이 완료되었습니다.")
                add_processing_log(session, job_id, "info", "completion", 
                                 f"작업 성공적으로 완료 - {duration}초 구간 추출")
            
            logger.info(f"[Job {job_id}] Range extraction completed: {output_path}")
            
        else:
            raise Exception("비디오 추출 실패")
    
    except Exception as e:
        logger.error(f"[Job {job_id}] Extraction error: {str(e)}")
        update_job_status_both(
            job_id,
            "failed",
            0,
            message="구간 추출 실패",
            error_message=str(e)
        )
        
        # 새 DB에도 실패 상태 업데이트
        with DatabaseManager.get_session() as session:
            update_job_status_db(session, job_id, "failed", 0, "구간 추출 실패", str(e))
            add_processing_log(session, job_id, "error", "failure", f"작업 실패: {str(e)}")


def create_multi_subtitle_file(ass_path: Path, subtitles: List[SubtitleInfo], offset: float, is_shorts: bool = False):
    """여러 자막이 포함된 ASS 파일 생성 - ASSGenerator 사용"""
    
    # ASSGenerator를 사용하여 생성
    generator = ASSGenerator()
    
    # 자막 데이터를 ASSGenerator 형식으로 변환
    subtitle_data = []
    
    # 실제 자막들 추가
    for subtitle in subtitles:
        sub_dict = {
            'start_time': subtitle.start - offset,
            'end_time': subtitle.end - offset
        }
        if subtitle.eng:
            sub_dict['eng'] = subtitle.eng
            sub_dict['english'] = subtitle.eng  # ASSGenerator 호환성
        if subtitle.kor:
            sub_dict['kor'] = subtitle.kor
            sub_dict['korean'] = subtitle.kor  # ASSGenerator 호환성
        
        subtitle_data.append(sub_dict)
    
    # ASS 파일 생성
    generator.generate_ass(subtitle_data, str(ass_path), is_shorts=is_shorts)
    
    logger.info(f"Created multi-subtitle file using ASSGenerator: {ass_path} with {len(subtitles)} subtitles")


# Alias endpoint for compatibility
@router.post("/clip/continuous",
             response_model=ClippingResponse,
             summary="연속 구간 클립 생성 (alias for extract/range)")
async def create_continuous_clip(
    request: ExtractRangeRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    /extract/range의 alias 엔드포인트입니다.
    기존 클라이언트와의 호환성을 위해 제공됩니다.
    """
    return await extract_range(request, background_tasks, req)