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
    
    # JWT Configuration (optional for now)
    JWT_SECRET = os.getenv('JWT_SECRET', 'not-used')
    
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
        warnings = []
        
        # Required configurations
        if not cls.DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is required")
        elif not cls.DISCORD_TOKEN.startswith(('Bot ', 'MTI', 'MTE', 'MTk')):
            warnings.append("DISCORD_TOKEN format may be incorrect (should start with 'Bot ' or be a valid bot token)")
        
        # Port validation
        if not (1024 <= cls.WEB_SERVER_PORT <= 65535):
            errors.append(f"WEB_SERVER_PORT must be between 1024-65535, got {cls.WEB_SERVER_PORT}")
        
        # Directory validation and creation
        db_dir = os.path.dirname(cls.DATABASE_PATH)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create database directory '{db_dir}': {e}")
        
        if not os.path.exists(cls.RECORDINGS_PATH):
            try:
                os.makedirs(cls.RECORDINGS_PATH, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create recordings directory '{cls.RECORDINGS_PATH}': {e}")
        
        # Test write permissions
        test_dirs = [(cls.RECORDINGS_PATH, "recordings"), (db_dir, "database") if db_dir else None]
        for dir_path, name in filter(None, test_dirs):
            try:
                test_file = os.path.join(dir_path, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception as e:
                errors.append(f"No write permission for {name} directory '{dir_path}': {e}")
        
        # Audio format validation
        if cls.AUDIO_FORMAT not in ['mp3', 'wav', 'aac']:
            warnings.append(f"AUDIO_FORMAT '{cls.AUDIO_FORMAT}' may not be supported")
        
        # Duration limits
        if cls.MAX_RECORDING_DURATION > 14400:  # 4 hours
            warnings.append(f"MAX_RECORDING_DURATION ({cls.MAX_RECORDING_DURATION}s) is very long")
        
        # Log level validation
        if cls.LOG_LEVEL.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            warnings.append(f"LOG_LEVEL '{cls.LOG_LEVEL}' is not standard, using INFO")
            cls.LOG_LEVEL = 'INFO'
        
        # Report warnings
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")
        
        # Fail on errors
        if errors:
            raise ValueError("Configuration errors: " + "; ".join(errors))
        
        return True

def setup_logging():
    """Setup logging configuration"""
    # Ensure logs directory exists
    os.makedirs('./logs', exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Setup handlers
    handlers = [
        logging.StreamHandler(),  # Console output
        logging.FileHandler('./logs/bot.log'),  # All logs
        logging.FileHandler('./logs/errors.log')  # Error logs only
    ]
    
    # Configure handlers
    handlers[0].setFormatter(simple_formatter)  # Console: simple format
    handlers[1].setFormatter(detailed_formatter)  # File: detailed format
    handlers[2].setFormatter(detailed_formatter)  # Error file: detailed format
    handlers[2].setLevel(logging.ERROR)  # Error file: only errors
    
    # Setup root logger
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        handlers=handlers
    )
    
    # Set discord.py logging level to WARNING to reduce noise
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('discord.client').setLevel(logging.WARNING)
    logging.getLogger('discord.voice_client').setLevel(logging.WARNING)
    
    # Set uvicorn logging level
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")