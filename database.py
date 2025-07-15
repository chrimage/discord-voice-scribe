import aiosqlite
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir:  # Only create directory if path has a directory component
                os.makedirs(db_dir, exist_ok=True)
            
            # Test write permissions
            test_path = f"{self.db_path}.test"
            try:
                with open(test_path, 'w') as f:
                    f.write('test')
                os.remove(test_path)
            except Exception as e:
                raise RuntimeError(f"No write permission for database path {self.db_path}: {e}")
            
            # Connect to database
            self.connection = await aiosqlite.connect(self.db_path)
            await self.connection.execute('PRAGMA foreign_keys = ON')
            
            # Test database connection
            await self.connection.execute('SELECT 1')
            
            # Create tables
            await self.create_tables()
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            if self.connection:
                await self.connection.close()
                self.connection = None
            raise
    
    async def create_tables(self):
        """Create database tables"""
        async with self.connection.execute('''
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                started_by INTEGER NOT NULL,
                started_by_name TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration INTEGER,
                file_path TEXT,
                file_size INTEGER,
                participants TEXT,
                status TEXT DEFAULT 'recording',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''):
            pass
        
        async with self.connection.execute('''
            CREATE TABLE IF NOT EXISTS download_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                recording_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recording_id) REFERENCES recordings (id)
            )
        '''):
            pass
        
        await self.connection.commit()
        logger.info("Database tables created successfully")
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            logger.info("Database connection closed")
    
    async def start_recording(self, guild_id: int, channel_id: int, channel_name: str, 
                            started_by: int, started_by_name: str) -> int:
        """Start a new recording and return its ID"""
        async with self.connection.execute('''
            INSERT INTO recordings (guild_id, channel_id, channel_name, started_by, 
                                  started_by_name, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, 'recording')
        ''', (guild_id, channel_id, channel_name, started_by, started_by_name, datetime.utcnow())):
            pass
        
        await self.connection.commit()
        
        # Get the recording ID
        async with self.connection.execute('SELECT last_insert_rowid()') as cursor:
            result = await cursor.fetchone()
            recording_id = result[0]
        
        logger.info(f"Started recording {recording_id} in guild {guild_id}, channel {channel_id}")
        return recording_id
    
    async def finish_recording(self, recording_id: int, file_path: str, file_size: int, 
                             participants: List[str], duration: int):
        """Mark recording as finished and update metadata"""
        await self.connection.execute('''
            UPDATE recordings 
            SET end_time = ?, file_path = ?, file_size = ?, participants = ?, 
                duration = ?, status = 'completed', updated_at = ?
            WHERE id = ?
        ''', (datetime.utcnow(), file_path, file_size, ','.join(participants), 
              duration, datetime.utcnow(), recording_id))
        
        await self.connection.commit()
        logger.info(f"Recording {recording_id} finished successfully")
    
    async def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get recording by ID"""
        async with self.connection.execute('''
            SELECT id, guild_id, channel_id, channel_name, started_by, started_by_name,
                   start_time, end_time, duration, file_path, file_size, participants, status
            FROM recordings WHERE id = ?
        ''', (recording_id,)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'guild_id': row[1],
                    'channel_id': row[2],
                    'channel_name': row[3],
                    'started_by': row[4],
                    'started_by_name': row[5],
                    'start_time': row[6],
                    'end_time': row[7],
                    'duration': row[8],
                    'file_path': row[9],
                    'file_size': row[10],
                    'participants': row[11].split(',') if row[11] else [],
                    'status': row[12]
                }
            return None
    
    async def get_guild_recordings(self, guild_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get recordings for a guild with pagination"""
        async with self.connection.execute('''
            SELECT id, guild_id, channel_id, channel_name, started_by, started_by_name,
                   start_time, end_time, duration, file_path, file_size, participants, status
            FROM recordings 
            WHERE guild_id = ? 
            ORDER BY start_time DESC 
            LIMIT ? OFFSET ?
        ''', (guild_id, limit, offset)) as cursor:
            rows = await cursor.fetchall()
            
            recordings = []
            for row in rows:
                recordings.append({
                    'id': row[0],
                    'guild_id': row[1],
                    'channel_id': row[2],
                    'channel_name': row[3],
                    'started_by': row[4],
                    'started_by_name': row[5],
                    'start_time': row[6],
                    'end_time': row[7],
                    'duration': row[8],
                    'file_path': row[9],
                    'file_size': row[10],
                    'participants': row[11].split(',') if row[11] else [],
                    'status': row[12]
                })
            
            return recordings
    
    async def get_active_recording(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get active recording for a guild"""
        async with self.connection.execute('''
            SELECT id, guild_id, channel_id, channel_name, started_by, started_by_name,
                   start_time, end_time, duration, file_path, file_size, participants, status
            FROM recordings 
            WHERE guild_id = ? AND status = 'recording'
            ORDER BY start_time DESC 
            LIMIT 1
        ''', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'guild_id': row[1],
                    'channel_id': row[2],
                    'channel_name': row[3],
                    'started_by': row[4],
                    'started_by_name': row[5],
                    'start_time': row[6],
                    'end_time': row[7],
                    'duration': row[8],
                    'file_path': row[9],
                    'file_size': row[10],
                    'participants': row[11].split(',') if row[11] else [],
                    'status': row[12]
                }
            return None
    
    async def create_download_token(self, token: str, recording_id: int, user_id: int, expires_at: datetime):
        """Create a download token"""
        await self.connection.execute('''
            INSERT INTO download_tokens (token, recording_id, user_id, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (token, recording_id, user_id, expires_at))
        
        await self.connection.commit()
        logger.info(f"Created download token for recording {recording_id}, user {user_id}")
    
    async def get_download_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get download token information"""
        async with self.connection.execute('''
            SELECT dt.token, dt.recording_id, dt.user_id, dt.expires_at, dt.used_at,
                   r.file_path, r.guild_id, r.started_by
            FROM download_tokens dt
            JOIN recordings r ON dt.recording_id = r.id
            WHERE dt.token = ?
        ''', (token,)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                return {
                    'token': row[0],
                    'recording_id': row[1],
                    'user_id': row[2],
                    'expires_at': row[3],
                    'used_at': row[4],
                    'file_path': row[5],
                    'guild_id': row[6],
                    'started_by': row[7]
                }
            return None
    
    async def mark_token_used(self, token: str):
        """Mark a download token as used"""
        await self.connection.execute('''
            UPDATE download_tokens 
            SET used_at = ? 
            WHERE token = ?
        ''', (datetime.utcnow(), token))
        
        await self.connection.commit()
    
    async def cleanup_expired_tokens(self):
        """Remove expired download tokens"""
        await self.connection.execute('''
            DELETE FROM download_tokens 
            WHERE expires_at < ?
        ''', (datetime.utcnow(),))
        
        await self.connection.commit()
        logger.info("Expired download tokens cleaned up")