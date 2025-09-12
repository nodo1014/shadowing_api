#!/usr/bin/env python3
"""
YouTube Clone Viewer Router - 생성된 영상을 유튜브처럼 보여주는 라우터
DB 연동 버전
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os
import sys
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database_v2.models_v2 import DatabaseManager, OutputVideo, Job, Subtitle

router = APIRouter(prefix="/viewer", tags=["viewer"])

# Templates setup
templates = Jinja2Templates(directory="templates")

# Database session dependency
def get_db():
    db_manager = DatabaseManager()
    try:
        yield db_manager.get_session()
    finally:
        db_manager.close()

def format_relative_time(timestamp: datetime) -> str:
    """상대적 시간 포맷"""
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 365:
        return f"{diff.days // 365} year{'s' if diff.days // 365 > 1 else ''} ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month{'s' if diff.days // 30 > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hour{'s' if diff.seconds // 3600 > 1 else ''} ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minute{'s' if diff.seconds // 60 > 1 else ''} ago"
    else:
        return "Just now"

def create_video_dict(video: OutputVideo, job: Job, subtitle: Optional[Subtitle] = None) -> Dict:
    """DB 모델을 비디오 정보 딕셔너리로 변환"""
    # 제목 생성
    if subtitle and subtitle.text_eng:
        # 자막에서 제목 생성 (첫 20자)
        title = subtitle.text_eng[:50] + "..." if len(subtitle.text_eng) > 50 else subtitle.text_eng
    else:
        # 파일명에서 제목 생성
        title_parts = video.file_name.replace('.mp4', '').replace('_', ' ').split()
        title = ' '.join(word.capitalize() for word in title_parts)
    
    # 비디오 ID 생성
    video_id = f"v{video.id}"
    
    # 조회수 업데이트
    if not video.view_count:
        video.view_count = 0
    
    return {
        "id": video_id,
        "db_id": video.id,
        "title": title,
        "path": video.file_path,
        "filename": video.file_name,
        "size": video.file_size or 0,
        "created": video.created_at,
        "views": f"{video.view_count} views",
        "duration": f"0:{int(video.duration or 30)}",  # 기본 30초
        "thumbnail": f"/viewer/api/thumbnail/{video_id}",
        "channel": "Shadowing Maker",
        "channel_icon": "/static/channel-icon.png",
        "uploaded": format_relative_time(video.created_at) if video.created_at else "Unknown",
        "template_id": job.template_id,
        "video_type": video.video_type,
        "effect_type": video.effect_type,
        "subtitle_mode": video.subtitle_mode
    }

@router.get("/", response_class=HTMLResponse)
async def viewer_home(request: Request, db: Session = Depends(get_db)):
    """메인 페이지 - 비디오 리스트 (DB 버전)"""
    
    # DB에서 비디오 목록 가져오기
    videos_query = (
        db.query(OutputVideo, Job, Subtitle)
        .join(Job, OutputVideo.job_id == Job.id)
        .outerjoin(Subtitle, Job.id == Subtitle.job_id)
        .filter(OutputVideo.video_type.in_(['final', 'preview']))  # 최종본과 프리뷰만
        .order_by(desc(OutputVideo.created_at))
        .limit(50)  # 최대 50개
    )
    
    videos = []
    for video, job, subtitle in videos_query:
        # 파일이 실제로 존재하는지 확인
        if os.path.exists(video.file_path):
            videos.append(create_video_dict(video, job, subtitle))
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "videos": videos,
        "title": "YouTube Clone - Shadowing Maker"
    })

@router.get("/watch/{video_id}", response_class=HTMLResponse)
async def viewer_watch(request: Request, video_id: str, db: Session = Depends(get_db)):
    """비디오 상세 페이지 (DB 버전)"""
    
    # video_id에서 실제 DB ID 추출 (v123 -> 123)
    try:
        db_id = int(video_id.replace('v', ''))
    except:
        raise HTTPException(status_code=404, detail="Invalid video ID")
    
    # 현재 비디오 가져오기
    result = (
        db.query(OutputVideo, Job, Subtitle)
        .join(Job, OutputVideo.job_id == Job.id)
        .outerjoin(Subtitle, Job.id == Subtitle.job_id)
        .filter(OutputVideo.id == db_id)
        .first()
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video, job, subtitle = result
    
    # 파일이 실제로 존재하는지 확인
    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # 조회수 증가
    video.view_count = (video.view_count or 0) + 1
    video.last_viewed_at = datetime.now()
    db.commit()
    
    current_video = create_video_dict(video, job, subtitle)
    
    # 자막 정보 추가
    if subtitle:
        current_video['subtitle_eng'] = subtitle.text_eng
        current_video['subtitle_kor'] = subtitle.text_kor
        current_video['note'] = subtitle.note
    
    # 추천 비디오 가져오기 (같은 템플릿 우선)
    recommendations_query = (
        db.query(OutputVideo, Job, Subtitle)
        .join(Job, OutputVideo.job_id == Job.id)
        .outerjoin(Subtitle, Job.id == Subtitle.job_id)
        .filter(
            OutputVideo.id != db_id,
            OutputVideo.video_type.in_(['final', 'preview'])
        )
        .order_by(
            # 같은 템플릿 우선
            (Job.template_id == job.template_id).desc(),
            desc(OutputVideo.created_at)
        )
        .limit(10)
    )
    
    recommendations = []
    for rec_video, rec_job, rec_subtitle in recommendations_query:
        if os.path.exists(rec_video.file_path):
            recommendations.append(create_video_dict(rec_video, rec_job, rec_subtitle))
    
    return templates.TemplateResponse("watch.html", {
        "request": request,
        "video": current_video,
        "recommendations": recommendations,
        "title": f"{current_video['title']} - YouTube Clone"
    })

@router.get("/api/thumbnail/{video_id}")
async def viewer_thumbnail(video_id: str, db: Session = Depends(get_db)):
    """썸네일 생성 (비디오 파일 자체 반환)"""
    
    # video_id에서 실제 DB ID 추출
    try:
        db_id = int(video_id.replace('v', ''))
    except:
        raise HTTPException(status_code=404, detail="Invalid video ID")
    
    # 비디오 정보 가져오기
    video = db.query(OutputVideo).filter(OutputVideo.id == db_id).first()
    
    if not video or not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 나중에 ffmpeg로 실제 썸네일 생성 구현
    # 지금은 비디오 파일 자체를 반환
    return FileResponse(video.file_path, media_type="video/mp4", headers={
        "Accept-Ranges": "bytes"
    })

@router.get("/api/videos")
async def viewer_api_videos(
    page: int = 1,
    per_page: int = 20,
    video_type: Optional[str] = None,
    template_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """API - 비디오 리스트 (DB 버전)"""
    
    # 쿼리 빌드
    query = (
        db.query(OutputVideo, Job, Subtitle)
        .join(Job, OutputVideo.job_id == Job.id)
        .outerjoin(Subtitle, Job.id == Subtitle.job_id)
    )
    
    # 필터 적용
    if video_type:
        query = query.filter(OutputVideo.video_type == video_type)
    else:
        query = query.filter(OutputVideo.video_type.in_(['final', 'preview']))
    
    if template_id:
        query = query.filter(Job.template_id == template_id)
    
    # 총 개수
    total = query.count()
    
    # 페이지네이션
    offset = (page - 1) * per_page
    results = query.order_by(desc(OutputVideo.created_at)).offset(offset).limit(per_page).all()
    
    videos = []
    for video, job, subtitle in results:
        if os.path.exists(video.file_path):
            videos.append(create_video_dict(video, job, subtitle))
    
    return {
        "videos": videos,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }

@router.get("/api/stats")
async def viewer_stats(db: Session = Depends(get_db)):
    """비디오 통계"""
    
    from sqlalchemy import func
    
    # 전체 통계
    total_videos = db.query(OutputVideo).count()
    total_views = db.query(func.sum(OutputVideo.view_count)).scalar() or 0
    
    # 템플릿별 통계
    template_stats = (
        db.query(
            Job.template_id,
            func.count(OutputVideo.id).label('count'),
            func.sum(OutputVideo.view_count).label('views')
        )
        .join(Job, OutputVideo.job_id == Job.id)
        .group_by(Job.template_id)
        .all()
    )
    
    # 가장 많이 본 비디오
    popular_videos_query = (
        db.query(OutputVideo, Job, Subtitle)
        .join(Job, OutputVideo.job_id == Job.id)
        .outerjoin(Subtitle, Job.id == Subtitle.job_id)
        .filter(OutputVideo.view_count > 0)
        .order_by(desc(OutputVideo.view_count))
        .limit(5)
    )
    
    popular_videos = []
    for video, job, subtitle in popular_videos_query:
        if os.path.exists(video.file_path):
            popular_videos.append(create_video_dict(video, job, subtitle))
    
    return {
        "total_videos": total_videos,
        "total_views": total_views,
        "template_stats": [
            {
                "template_id": stat.template_id,
                "count": stat.count,
                "views": stat.views or 0
            }
            for stat in template_stats
        ],
        "popular_videos": popular_videos
    }