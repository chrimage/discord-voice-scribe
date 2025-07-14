import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""
    
    # Discord Bot Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    # JWT Configuration
    JWT_SECRET = os.getenv('JWT_SECRET')
    if not JWT_SECRET:
        raise ValueError("JWT_SECRET environment variable is required")
    
    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', './data/recordings.db')
    
    # File Storage Configuration
    RECORDINGS_PATH = os.getenv('RECORDINGS_PATH', './recordings')
    
    # Web Server Configuration
    WEB_SERVER_HOST = os.getenv('WEB_SERVER_HOST', '0.0.0.0')
    WEB_SERVER_PORT = int(os.getenv('WEB_SERVER_PORT', '8000'))
    
    # Audio Processing Configuration
    AUDIO_QUALITY = os.getenv('AUDIO_QUALITY', '192k')
    AUDIO_FORMAT = os.getenv('AUDIO_FORMAT', 'mp3')
    MAX_RECORDING_DURATION = int(os.getenv('MAX_RECORDING_DURATION', '7200'))  # 2 hours
    CLEANUP_AFTER_HOURS = int(os.getenv('CLEANUP_AFTER_HOURS', '24'))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        if not cls.DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is required")
        
        if not cls.JWT_SECRET:
            errors.append("JWT_SECRET is required")
        
        if not os.path.exists(os.path.dirname(cls.DATABASE_PATH)):
            try:
                os.makedirs(os.path.dirname(cls.DATABASE_PATH), exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create database directory: {e}")
        
        if not os.path.exists(cls.RECORDINGS_PATH):
            try:
                os.makedirs(cls.RECORDINGS_PATH, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create recordings directory: {e}")
        
        if errors:
            raise ValueError("Configuration errors: " + ", ".join(errors))
        
        return True

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log')
        ]
    )
    
    # Set discord.py logging level to WARNING to reduce noise
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('discord.client').setLevel(logging.WARNING)