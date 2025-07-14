import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

logger = logging.getLogger(__name__)

class FileServer:
    """Secure file server for serving audio recordings"""
    
    def __init__(self, recordings_path: str, jwt_secret: str):
        self.recordings_path = Path(recordings_path)
        self.jwt_secret = jwt_secret
        self.app = FastAPI(title="Discord Voice Recording Server")
        self.server = None
        self.security = HTTPBearer()
        
        # Setup routes
        self.setup_routes()
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
        
        @self.app.get("/download/{token}")
        async def download_file(token: str):
            """Download file with token authentication"""
            try:
                # Verify and decode token
                payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
                
                # Check if token is still valid
                if datetime.utcnow() > datetime.fromisoformat(payload['expires_at']):
                    raise HTTPException(status_code=403, detail="Token expired")
                
                # Get file path from token
                file_path = Path(payload['file_path'])
                
                # Security check: ensure file is within recordings directory
                if not file_path.is_absolute():
                    file_path = self.recordings_path / file_path
                
                # Resolve path and check it's within recordings directory
                file_path = file_path.resolve()
                if not str(file_path).startswith(str(self.recordings_path.resolve())):
                    raise HTTPException(status_code=403, detail="Access denied")
                
                # Check if file exists
                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Return file
                return FileResponse(
                    path=str(file_path),
                    filename=f"recording_{payload['recording_id']}.{file_path.suffix.lstrip('.')}",
                    media_type='audio/mpeg' if file_path.suffix == '.mp3' else 'audio/wav'
                )
                
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=403, detail="Invalid token")
            except Exception as e:
                logger.error(f"Error serving file: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc):
            return {"error": "Not found"}
        
        @self.app.exception_handler(500)
        async def internal_error_handler(request: Request, exc):
            return {"error": "Internal server error"}
    
    def generate_download_token(self, recording_id: int, file_path: str, 
                              user_id: int, expires_hours: int = 1) -> str:
        """Generate a secure download token"""
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        payload = {
            'recording_id': recording_id,
            'file_path': file_path,
            'user_id': user_id,
            'expires_at': expires_at.isoformat(),
            'issued_at': datetime.utcnow().isoformat(),
            'random': secrets.token_urlsafe(16)  # Add randomness
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        logger.info(f"Generated download token for recording {recording_id}, user {user_id}")
        return token
    
    def get_download_url(self, token: str, base_url: str = "http://localhost:8000") -> str:
        """Get download URL for a token"""
        return f"{base_url}/download/{token}"
    
    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the file server"""
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=False  # Disable access logs to reduce noise
        )
        
        self.server = uvicorn.Server(config)
        
        # Start server in background
        asyncio.create_task(self.server.serve())
        logger.info(f"File server started on {host}:{port}")
    
    async def stop(self):
        """Stop the file server"""
        if self.server:
            self.server.should_exit = True
            logger.info("File server stopped")
    
    def validate_file_access(self, file_path: str, user_id: int) -> bool:
        """Validate that a user can access a file"""
        # Additional validation logic can be added here
        # For now, we rely on the token-based authentication
        return True