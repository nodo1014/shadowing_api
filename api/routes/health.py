"""
Health Check Routes
"""
import os
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from api.models import ALLOWED_MEDIA_ROOTS

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """웹 인터페이스 제공"""
    return FileResponse("index.html")


@router.get("/admin", response_class=FileResponse)
async def admin_page():
    """관리자 페이지"""
    admin_file = Path("admin.html")
    if admin_file.exists():
        return FileResponse(admin_file)
    else:
        # admin.html이 없으면 기본 페이지
        return HTMLResponse(content="<h1>Admin Page Not Found</h1>", status_code=404)


@router.get("/restful", response_class=HTMLResponse, include_in_schema=False)
async def api_docs():
    """REST API 문서"""
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Clipping API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .endpoint { margin: 20px 0; padding: 15px; background: #f5f5f5; }
            .method { font-weight: bold; }
            .get { color: #61affe; }
            .post { color: #49cc90; }
            .delete { color: #f93e3e; }
            code { background: #e8e8e8; padding: 2px 5px; }
        </style>
    </head>
    <body>
        <h1>Video Clipping REST API</h1>
        
        <div class="endpoint">
            <h3><span class="method post">POST</span> /api/clip</h3>
            <p>Create a single clip</p>
            <pre><code>{
  "media_path": "/path/to/video.mp4",
  "start_time": 10.5,
  "end_time": 15.5,
  "text_eng": "English text",
  "text_kor": "Korean text",
  "template_number": 1,
  "individual_clips": true
}</code></pre>
        </div>
        
        <div class="endpoint">
            <h3><span class="method post">POST</span> /api/clip/batch</h3>
            <p>Create multiple clips from same video</p>
            <pre><code>{
  "media_path": "/path/to/video.mp4",
  "clips": [
    {
      "start_time": 10.5,
      "end_time": 15.5,
      "text_eng": "First clip",
      "text_kor": "첫 번째 클립"
    },
    {
      "start_time": 20.0,
      "end_time": 25.0,
      "text_eng": "Second clip",
      "text_kor": "두 번째 클립"
    }
  ],
  "template_number": 11,
  "title_1": "영어 마스터하기",
  "title_2": "오늘의 표현"
}</code></pre>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span> /api/status/{job_id}</h3>
            <p>Check job status</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span> /api/download/{job_id}</h3>
            <p>Download completed video</p>
        </div>
        
        <p>For detailed API documentation, visit <a href="/docs">/docs</a></p>
    </body>
    </html>
    '''
    return HTMLResponse(content=html_content)


@router.get("/api")
async def api_info():
    """API 정보"""
    return {
        "name": "Video Clipping API",
        "version": "1.0.0",
        "description": "Professional video clipping service with subtitle support",
        "endpoints": {
            "clip": "/api/clip",
            "batch": "/api/clip/batch", 
            "status": "/api/status/{job_id}",
            "download": "/api/download/{job_id}"
        }
    }


@router.get("/api/allowed-roots")
async def get_allowed_roots():
    """허용된 미디어 루트 디렉토리 목록"""
    roots_info = []
    for root in ALLOWED_MEDIA_ROOTS:
        if root.exists():
            try:
                # 디렉토리 내용 샘플링
                sample_files = []
                for item in list(root.iterdir())[:5]:
                    if item.is_file() and item.suffix.lower() in ['.mp4', '.mkv', '.avi']:
                        sample_files.append(item.name)
                
                roots_info.append({
                    "path": str(root),
                    "exists": True,
                    "sample_files": sample_files
                })
            except PermissionError:
                roots_info.append({
                    "path": str(root),
                    "exists": True,
                    "sample_files": [],
                    "error": "Permission denied"
                })
        else:
            roots_info.append({
                "path": str(root),
                "exists": False
            })
    
    return {
        "allowed_roots": roots_info,
        "supported_formats": ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.flv']
    }


@router.get("/health")
async def health_check():
    """헬스체크"""
    return {"status": "healthy"}