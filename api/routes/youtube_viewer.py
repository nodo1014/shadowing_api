#!/usr/bin/env python3
"""
YouTube Clone Viewer Router - 생성된 영상을 유튜브처럼 보여주는 라우터
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os
import glob
import hashlib
from typing import List, Dict
from pathlib import Path

router = APIRouter(prefix="/viewer", tags=["viewer"])

# Templates setup
templates = Jinja2Templates(directory="templates")

def get_video_info(video_path: str) -> Dict:
    """비디오 파일 정보 추출"""
    file_stat = os.stat(video_path)
    file_name = os.path.basename(video_path)
    
    # 파일명에서 제목 추출
    title_parts = file_name.replace('.mp4', '').replace('_', ' ').split()
    title = ' '.join(word.capitalize() for word in title_parts)
    
    # 간단한 해시로 고유 ID 생성
    video_id = hashlib.md5(video_path.encode()).hexdigest()[:11]
    
    # 썸네일 생성 (첫 프레임 추출 - 실제로는 ffmpeg 필요)
    thumbnail = f"/viewer/api/thumbnail/{video_id}"
    
    return {
        "id": video_id,
        "title": title,
        "path": video_path,
        "filename": file_name,
        "size": file_stat.st_size,
        "created": datetime.fromtimestamp(file_stat.st_mtime),
        "views": f"{hash(video_path) % 1000}K views",  # 가짜 조회수
        "duration": "0:30",  # Shorts는 보통 30초
        "thumbnail": thumbnail,
        "channel": "Shadowing Maker",
        "channel_icon": "/static/channel-icon.png",
        "uploaded": format_relative_time(file_stat.st_mtime)
    }

def format_relative_time(timestamp: float) -> str:
    """상대적 시간 포맷"""
    now = datetime.now()
    created = datetime.fromtimestamp(timestamp)
    diff = now - created
    
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

@router.get("/", response_class=HTMLResponse)
async def viewer_home(request: Request):
    """메인 페이지 - 비디오 리스트"""
    # shorts_output 디렉토리의 모든 mp4 파일 찾기
    video_files = glob.glob("shorts_output/**/*.mp4", recursive=True)
    # output 디렉토리도 확인
    video_files.extend(glob.glob("output/**/*.mp4", recursive=True))
    
    videos = [get_video_info(vf) for vf in video_files if os.path.exists(vf)]
    
    # 최신순으로 정렬
    videos.sort(key=lambda x: x['created'], reverse=True)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "videos": videos,
        "title": "YouTube Clone - Shadowing Maker"
    })

@router.get("/watch/{video_id}", response_class=HTMLResponse)
async def viewer_watch(request: Request, video_id: str):
    """비디오 상세 페이지"""
    # 모든 비디오 찾기
    video_files = glob.glob("shorts_output/**/*.mp4", recursive=True)
    video_files.extend(glob.glob("output/**/*.mp4", recursive=True))
    videos = [get_video_info(vf) for vf in video_files]
    
    # 현재 비디오 찾기
    current_video = None
    for video in videos:
        if video['id'] == video_id:
            current_video = video
            break
    
    if not current_video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 추천 비디오 (현재 비디오 제외)
    recommendations = [v for v in videos if v['id'] != video_id]
    
    return templates.TemplateResponse("watch.html", {
        "request": request,
        "video": current_video,
        "recommendations": recommendations[:10],  # 최대 10개
        "title": f"{current_video['title']} - YouTube Clone"
    })

@router.get("/api/thumbnail/{video_id}")
async def viewer_thumbnail(video_id: str):
    """썸네일 생성 (임시로 첫 프레임 대신 placeholder 반환)"""
    # 실제로는 ffmpeg를 사용해 첫 프레임 추출 필요
    # 지금은 간단히 비디오 파일 자체를 반환
    video_files = glob.glob("shorts_output/**/*.mp4", recursive=True)
    video_files.extend(glob.glob("output/**/*.mp4", recursive=True))
    
    for vf in video_files:
        if hashlib.md5(vf.encode()).hexdigest()[:11] == video_id:
            # 실제 썸네일이 없으므로 placeholder 이미지 반환
            # 나중에 ffmpeg로 실제 썸네일 생성 구현
            return FileResponse(vf, media_type="video/mp4", headers={
                "Accept-Ranges": "bytes"
            })
    raise HTTPException(status_code=404, detail="Thumbnail not found")

@router.get("/api/videos")
async def viewer_api_videos():
    """API - 비디오 리스트"""
    video_files = glob.glob("shorts_output/**/*.mp4", recursive=True)
    video_files.extend(glob.glob("output/**/*.mp4", recursive=True))
    videos = [get_video_info(vf) for vf in video_files if os.path.exists(vf)]
    videos.sort(key=lambda x: x['created'], reverse=True)
    return {"videos": videos, "total": len(videos)}