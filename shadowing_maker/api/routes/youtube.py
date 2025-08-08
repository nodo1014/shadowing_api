"""
YouTube upload API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import sys
import json

sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from shadowing_maker.core.youtube.uploader import YouTubeUploader
from database_adapter import get_job_by_id, update_job_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/youtube", tags=["youtube"])

# YouTube uploader instance
uploader = YouTubeUploader()


class YouTubeUploadRequest(BaseModel):
    """YouTube upload request"""
    job_id: str = Field(..., description="Job ID to upload")
    title: str = Field(..., description="Video title")
    description: str = Field("", description="Video description")
    tags: List[str] = Field(default_factory=list, description="Video tags")
    privacy_status: str = Field("private", description="Privacy status: private, unlisted, public")


@router.get("/auth")
async def get_auth_url():
    """Get YouTube OAuth2 authorization URL"""
    try:
        auth_url = uploader.get_auth_url()
        return {
            "auth_url": auth_url,
            "message": "Please visit the URL to authorize YouTube access"
        }
    except Exception as e:
        logger.error(f"Failed to get auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def handle_auth_callback(request: Request):
    """Handle OAuth2 callback from Google"""
    try:
        # Get the full URL
        full_url = str(request.url)
        
        # Handle the callback
        result = uploader.handle_auth_callback(full_url)
        
        # Redirect to success page or return JSON
        return HTMLResponse(content="""
            <html>
                <head>
                    <title>YouTube 인증 완료</title>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 50px; text-align: center; }
                        .success { color: green; font-size: 24px; margin: 20px; }
                        .info { margin: 20px; padding: 20px; background: #f0f0f0; border-radius: 5px; }
                        button { padding: 10px 20px; font-size: 16px; cursor: pointer; }
                    </style>
                </head>
                <body>
                    <div class="success">✓ YouTube 인증이 완료되었습니다!</div>
                    <div class="info">
                        <p>채널: {channel_title}</p>
                        <p>구독자: {subscriber_count}명</p>
                        <p>동영상: {video_count}개</p>
                    </div>
                    <button onclick="window.close()">창 닫기</button>
                    <script>
                        // Notify parent window
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'youtube_auth_success', channel: {channel_json}}}, '*');
                        }}
                    </script>
                </body>
            </html>
        """.format(
            channel_title=result['channel'].get('title', 'Unknown'),
            subscriber_count=result['channel'].get('subscriber_count', '0'),
            video_count=result['channel'].get('video_count', '0'),
            channel_json=str(result['channel']).replace("'", '"')
        ))
        
    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        return HTMLResponse(content=f"""
            <html>
                <head><title>인증 실패</title></head>
                <body>
                    <h1>YouTube 인증 실패</h1>
                    <p>오류: {str(e)}</p>
                    <button onclick="window.close()">창 닫기</button>
                </body>
            </html>
        """)


@router.get("/status")
async def check_auth_status():
    """Check if YouTube is authenticated"""
    try:
        authenticated = uploader.load_saved_credentials()
        
        if authenticated:
            channel_info = uploader._get_channel_info()
            return {
                "authenticated": True,
                "channel": channel_info
            }
        else:
            return {
                "authenticated": False,
                "message": "Not authenticated. Please authorize first."
            }
            
    except Exception as e:
        logger.error(f"Failed to check auth status: {e}")
        return {
            "authenticated": False,
            "error": str(e)
        }


async def upload_to_youtube_task(job_id: str, title: str, description: str, tags: List[str], privacy_status: str):
    """Background task to upload video to YouTube"""
    try:
        # Get job data
        job_data = get_job_by_id(job_id)
        if not job_data:
            logger.error(f"Job not found: {job_id}")
            return
        
        video_path = job_data.get('output_file')
        if not video_path or not Path(video_path).exists():
            logger.error(f"Video file not found for job {job_id}")
            update_job_status(job_id, "failed", error="Video file not found")
            return
        
        # Update status to uploading
        update_job_status(job_id, "uploading", message="Uploading to YouTube...")
        
        # Upload to YouTube
        result = uploader.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status
        )
        
        if result['success']:
            update_job_status(
                job_id, "uploaded",
                message=f"Uploaded to YouTube: {result['video_url']}",
                output_file=video_path,
                results={"youtube": result}
            )
            logger.info(f"Successfully uploaded job {job_id} to YouTube: {result['video_id']}")
        else:
            update_job_status(
                job_id, "upload_failed",
                error=result.get('error', 'Unknown error')
            )
            logger.error(f"Failed to upload job {job_id}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Upload task error: {e}")
        update_job_status(job_id, "upload_failed", error=str(e))


@router.post("/upload")
async def upload_to_youtube(request: YouTubeUploadRequest, background_tasks: BackgroundTasks):
    """Upload a completed job to YouTube"""
    try:
        # Check if authenticated
        if not uploader.load_saved_credentials():
            raise HTTPException(status_code=401, detail="Not authenticated with YouTube")
        
        # Check if job exists and is completed
        job_data = get_job_by_id(request.job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data['status'] != 'completed':
            raise HTTPException(status_code=400, detail="Job is not completed yet")
        
        # Start background upload task
        background_tasks.add_task(
            upload_to_youtube_task,
            request.job_id,
            request.title,
            request.description,
            request.tags,
            request.privacy_status
        )
        
        return {
            "message": "Upload started",
            "job_id": request.job_id,
            "title": request.title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/{video_id}/status")
async def get_video_status(video_id: str):
    """Get YouTube video processing status"""
    try:
        status = uploader.get_upload_status(video_id)
        return status
    except Exception as e:
        logger.error(f"Failed to get video status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class YouTubeSettingsRequest(BaseModel):
    """YouTube API settings request"""
    client_id: str = Field(..., description="OAuth2 Client ID")
    client_secret: str = Field(..., description="OAuth2 Client Secret")
    project_id: str = Field("shadowing-maker", description="Google Cloud Project ID")


@router.get("/settings")
async def get_youtube_settings():
    """Get YouTube API settings (without secrets)"""
    try:
        settings_file = Path("client_secrets.json")
        
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                data = json.load(f)
                
            # Extract settings without exposing full secret
            if "installed" in data:
                client_data = data["installed"]
            elif "web" in data:
                client_data = data["web"]
            else:
                client_data = {}
            
            return {
                "configured": bool(client_data.get("client_id")),
                "client_id": client_data.get("client_id", ""),
                "project_id": client_data.get("project_id", ""),
                # Mask the client secret
                "client_secret": "****" + client_data.get("client_secret", "")[-4:] if client_data.get("client_secret") else ""
            }
        else:
            return {
                "configured": False,
                "client_id": "",
                "project_id": "",
                "client_secret": ""
            }
            
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        return {
            "configured": False,
            "error": str(e)
        }


@router.post("/settings")
async def save_youtube_settings(request: YouTubeSettingsRequest):
    """Save YouTube API settings"""
    try:
        # Create client secrets JSON structure
        client_secrets = {
            "installed": {
                "client_id": request.client_id,
                "project_id": request.project_id,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": request.client_secret,
                "redirect_uris": ["http://localhost:8080/api/youtube/callback"]
            }
        }
        
        # Save to file
        settings_file = Path("client_secrets.json")
        with open(settings_file, 'w') as f:
            json.dump(client_secrets, f, indent=2)
        
        # Reinitialize uploader with new settings
        global uploader
        uploader = YouTubeUploader(client_secrets_file=str(settings_file))
        
        logger.info("YouTube API settings saved successfully")
        return {
            "success": True,
            "message": "Settings saved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/test")
async def test_youtube_settings():
    """Test YouTube API settings"""
    try:
        settings_file = Path("client_secrets.json")
        
        if not settings_file.exists():
            return {
                "success": False,
                "error": "Settings not configured"
            }
        
        # Try to load the settings
        with open(settings_file, 'r') as f:
            data = json.load(f)
        
        # Check required fields
        if "installed" in data:
            client_data = data["installed"]
        elif "web" in data:
            client_data = data["web"]
        else:
            return {
                "success": False,
                "error": "Invalid client secrets format"
            }
        
        if not client_data.get("client_id") or not client_data.get("client_secret"):
            return {
                "success": False,
                "error": "Missing client_id or client_secret"
            }
        
        # Settings are valid (we can't test actual API connection without OAuth flow)
        return {
            "success": True,
            "message": "Settings are valid. Use 'Connect YouTube' to authenticate."
        }
        
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid JSON format in settings file"
        }
    except Exception as e:
        logger.error(f"Settings test failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }