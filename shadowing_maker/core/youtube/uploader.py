"""
YouTube video uploader module
"""
import os
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeUploader:
    """YouTube video upload handler"""
    
    # YouTube OAuth2 scopes
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    API_SERVICE_NAME = 'youtube'
    API_VERSION = 'v3'
    
    def __init__(self, client_secrets_file: Optional[str] = None):
        """
        Initialize YouTube uploader
        
        Args:
            client_secrets_file: Path to client secrets JSON file from Google Console
        """
        self.client_secrets_file = client_secrets_file or os.getenv('YOUTUBE_CLIENT_SECRETS', 'client_secrets.json')
        self.credentials = None
        self.youtube = None
        
    def get_auth_url(self, redirect_uri: str = 'http://localhost:8080/api/youtube/callback') -> str:
        """
        Get OAuth2 authorization URL
        
        Args:
            redirect_uri: OAuth2 callback URL
            
        Returns:
            Authorization URL for user to visit
        """
        flow = Flow.from_client_secrets_file(
            self.client_secrets_file,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return auth_url
    
    def handle_auth_callback(self, authorization_response: str, redirect_uri: str = 'http://localhost:8080/api/youtube/callback') -> Dict[str, Any]:
        """
        Handle OAuth2 callback and save credentials
        
        Args:
            authorization_response: Full callback URL with code
            redirect_uri: OAuth2 callback URL
            
        Returns:
            User info and channel details
        """
        flow = Flow.from_client_secrets_file(
            self.client_secrets_file,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Exchange authorization code for credentials
        flow.fetch_token(authorization_response=authorization_response)
        self.credentials = flow.credentials
        
        # Save credentials for future use
        self._save_credentials(self.credentials)
        
        # Build YouTube service
        self.youtube = build(
            self.API_SERVICE_NAME,
            self.API_VERSION,
            credentials=self.credentials
        )
        
        # Get channel info
        channel_info = self._get_channel_info()
        
        return {
            'authenticated': True,
            'channel': channel_info
        }
    
    def load_saved_credentials(self) -> bool:
        """
        Load saved credentials if available
        
        Returns:
            True if credentials loaded successfully
        """
        creds_file = Path('youtube_credentials.json')
        
        if not creds_file.exists():
            return False
        
        try:
            with open(creds_file, 'r') as f:
                creds_data = json.load(f)
            
            self.credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data.get('refresh_token'),
                token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=creds_data.get('client_id'),
                client_secret=creds_data.get('client_secret'),
                scopes=self.SCOPES
            )
            
            self.youtube = build(
                self.API_SERVICE_NAME,
                self.API_VERSION,
                credentials=self.credentials
            )
            
            logger.info("Loaded saved YouTube credentials")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return False
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = '',
        tags: Optional[list] = None,
        category_id: str = '27',  # Education category
        privacy_status: str = 'private',
        thumbnail_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload video to YouTube
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID (27 = Education)
            privacy_status: 'private', 'unlisted', or 'public'
            thumbnail_path: Optional thumbnail image path
            
        Returns:
            Upload result with video ID and URL
        """
        if not self.youtube:
            if not self.load_saved_credentials():
                raise Exception("Not authenticated. Please authenticate first.")
        
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Execute upload
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            error = None
            retry = 0
            
            logger.info(f"Starting upload: {title}")
            
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        logger.info(f"Upload progress: {progress}%")
                        
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Retry on server errors
                        error = f"HTTP error {e.resp.status}: {e.content}"
                        retry += 1
                        if retry > 3:
                            raise
                        logger.warning(f"Retrying upload... (attempt {retry})")
                    else:
                        raise
            
            if response:
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                logger.info(f"Upload successful! Video ID: {video_id}")
                
                # Upload thumbnail if provided
                if thumbnail_path and Path(thumbnail_path).exists():
                    self._upload_thumbnail(video_id, thumbnail_path)
                
                return {
                    'success': True,
                    'video_id': video_id,
                    'video_url': video_url,
                    'title': title,
                    'privacy_status': privacy_status
                }
            
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """Upload thumbnail for video"""
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            logger.info(f"Thumbnail uploaded for video {video_id}")
        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
    
    def _get_channel_info(self) -> Dict[str, Any]:
        """Get authenticated user's channel info"""
        try:
            response = self.youtube.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if response['items']:
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'description': channel['snippet'].get('description', ''),
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                    'video_count': channel['statistics'].get('videoCount', '0')
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return {}
    
    def _save_credentials(self, credentials: Credentials):
        """Save credentials to file for future use"""
        creds_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        with open('youtube_credentials.json', 'w') as f:
            json.dump(creds_data, f)
        
        logger.info("Saved YouTube credentials")
    
    def get_upload_status(self, video_id: str) -> Dict[str, Any]:
        """
        Get status of uploaded video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video status information
        """
        if not self.youtube:
            if not self.load_saved_credentials():
                raise Exception("Not authenticated")
        
        try:
            response = self.youtube.videos().list(
                part='status,snippet,processingDetails',
                id=video_id
            ).execute()
            
            if response['items']:
                video = response['items'][0]
                return {
                    'video_id': video_id,
                    'title': video['snippet']['title'],
                    'upload_status': video['status']['uploadStatus'],
                    'privacy_status': video['status']['privacyStatus'],
                    'processing_status': video.get('processingDetails', {}).get('processingStatus', 'unknown'),
                    'video_url': f"https://www.youtube.com/watch?v={video_id}"
                }
            
            return {'error': 'Video not found'}
            
        except Exception as e:
            logger.error(f"Failed to get video status: {e}")
            return {'error': str(e)}