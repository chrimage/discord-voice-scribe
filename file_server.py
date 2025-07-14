import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
import uvicorn

logger = logging.getLogger(__name__)

class FileServer:
    """Simple file server for serving audio recordings with token-based access"""
    
    def __init__(self, recordings_path: str, jwt_secret: str = None):
        self.recordings_path = Path(recordings_path)
        self.app = FastAPI(title="Discord Voice Recording Server")
        self.server = None
        
        # Token storage: token -> {file_path, expires_at, recording_id}
        self.active_tokens: Dict[str, Dict] = {}
        
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
            """Download file with simple token authentication"""
            try:
                # Check if token exists
                if token not in self.active_tokens:
                    raise HTTPException(status_code=404, detail="File not found")
                
                token_info = self.active_tokens[token]
                
                # Check if token is still valid
                if datetime.utcnow() > token_info['expires_at']:
                    # Clean up expired token
                    del self.active_tokens[token]
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Get file path
                file_path = Path(token_info['file_path'])
                
                # Security check: ensure file is within recordings directory
                if not file_path.is_absolute():
                    file_path = self.recordings_path / file_path
                
                # Resolve path and check it's within recordings directory
                file_path = file_path.resolve()
                if not str(file_path).startswith(str(self.recordings_path.resolve())):
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Check if file exists
                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Return file
                return FileResponse(
                    path=str(file_path),
                    filename=f"recording_{token_info['recording_id']}.{file_path.suffix.lstrip('.')}",
                    media_type='audio/mpeg' if file_path.suffix == '.mp3' else 'audio/wav'
                )
                
            except Exception as e:
                logger.error(f"Error serving file: {e}")
                raise HTTPException(status_code=404, detail="File not found")
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc):
            return {"error": "Not found"}
        
        @self.app.exception_handler(500)
        async def internal_error_handler(request: Request, exc):
            return {"error": "Internal server error"}
    
    def generate_download_token(self, recording_id: int, file_path: str, 
                              user_id: int, expires_hours: int = 1) -> str:
        """Generate a random download token"""
        # Generate a long, random token (256 bits = 43 characters base64)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        # Store token info in memory
        self.active_tokens[token] = {
            'recording_id': recording_id,
            'file_path': file_path,
            'user_id': user_id,
            'expires_at': expires_at,
            'created_at': datetime.utcnow()
        }
        
        logger.info(f"Generated download token for recording {recording_id}, user {user_id}, expires in {expires_hours}h")
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
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired tokens from memory"""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, info in self.active_tokens.items() 
            if info['expires_at'] < now
        ]
        
        for token in expired_tokens:
            del self.active_tokens[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired download tokens")
        
        return len(expired_tokens)
    
    def get_active_token_count(self) -> int:
        """Get number of active tokens"""
        return len(self.active_tokens)