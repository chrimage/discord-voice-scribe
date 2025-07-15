import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    """Application configuration loaded from YAML file"""
    
    # Default configuration
    _defaults = {
        'discord': {
            'token': None,
            'activity': {
                'type': 'listening',
                'name': 'voice channels | /join to start recording'
            }
        },
        'database': {
            'path': './data/recordings.db',
            'connection': {
                'timeout': 30,
                'check_same_thread': False
            }
        },
        'storage': {
            'recordings_path': './recordings',
            'cleanup_after_hours': 24,
            'organize_by_date': True,
            'max_file_size_mb': 500
        },
        'audio': {
            'quality': '192k',
            'format': 'mp3',
            'sample_rate': 48000,
            'channels': 2,
            'max_duration_seconds': 7200,
            'silence_threshold': -40,
            'normalize_audio': True,
            'remove_silence': False,
            'fade_in_seconds': 0.5,
            'fade_out_seconds': 1.0
        },
        'web_server': {
            'host': '0.0.0.0',
            'port': 8000,
            'download_token_expires_hours': 1,
            'max_concurrent_downloads': 10,
            'ssl': {
                'enabled': False,
                'cert_file': '',
                'key_file': ''
            }
        },
        'logging': {
            'level': 'INFO',
            'file': {
                'enabled': True,
                'path': './logs/bot.log',
                'max_size_mb': 10,
                'backup_count': 5
            },
            'error_file': {
                'enabled': True,
                'path': './logs/errors.log'
            },
            'console': {
                'enabled': True,
                'format': 'simple'
            },
            'discord_log_level': 'WARNING'
        },
        'features': {
            'slash_commands': True,
            'voice_recording': True,
            'file_serving': True,
            'auto_cleanup': True,
            'experimental': {
                'voice_activity_detection': False,
                'real_time_transcription': False,
                'multi_channel_recording': False
            }
        },
        'permissions': {
            'recording': {
                'required_permissions': ['connect', 'speak'],
                'allowed_roles': [],
                'blocked_users': []
            },
            'download': {
                'creator_only': False,
                'same_guild_only': True,
                'max_downloads_per_user': 10
            },
            'admin': {
                'required_permissions': ['manage_messages'],
                'allowed_users': []
            }
        },
        'notifications': {
            'recording_started': True,
            'recording_stopped': True,
            'processing_complete': True,
            'errors': True,
            'channels': {
                'log_channel': None,
                'error_channel': None
            },
            'mentions': {
                'recording_creator': True,
                'participants': False
            }
        },
        'advanced': {
            'max_concurrent_recordings': 5,
            'audio_buffer_size': 4096,
            'processing_threads': 2,
            'max_retries': 3,
            'retry_delay_seconds': 5,
            'max_memory_usage_mb': 1024,
            'garbage_collection_interval': 300,
            'debug_mode': False,
            'profiling_enabled': False
        }
    }
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize configuration from YAML file"""
        self.config_path = config_path
        self._config = self._load_config()
        
        # Legacy compatibility properties
        self.DISCORD_TOKEN = self.get('discord.token')
        self.DATABASE_PATH = self.get('database.path')
        self.RECORDINGS_PATH = self.get('storage.recordings_path')
        self.WEB_SERVER_HOST = self.get('web_server.host')
        self.WEB_SERVER_PORT = self.get('web_server.port')
        self.AUDIO_QUALITY = self.get('audio.quality')
        self.AUDIO_FORMAT = self.get('audio.format')
        self.MAX_RECORDING_DURATION = self.get('audio.max_duration_seconds')
        self.CLEANUP_AFTER_HOURS = self.get('storage.cleanup_after_hours')
        self.LOG_LEVEL = self.get('logging.level')
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config = self._defaults.copy()
        
        # Try to load from YAML file
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        config = self._merge_configs(config, file_config)
            except Exception as e:
                raise ValueError(f"Failed to load config from {self.config_path}: {e}")
        
        # Override with environment variables if they exist (for Docker compatibility)
        env_overrides = {
            'DISCORD_TOKEN': 'discord.token',
            'DATABASE_PATH': 'database.path',
            'RECORDINGS_PATH': 'storage.recordings_path',
            'WEB_SERVER_HOST': 'web_server.host',
            'WEB_SERVER_PORT': 'web_server.port',
            'AUDIO_QUALITY': 'audio.quality',
            'AUDIO_FORMAT': 'audio.format',
            'MAX_RECORDING_DURATION': 'audio.max_duration_seconds',
            'CLEANUP_AFTER_HOURS': 'storage.cleanup_after_hours',
            'LOG_LEVEL': 'logging.level'
        }
        
        for env_var, config_path in env_overrides.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                if env_var in ['WEB_SERVER_PORT', 'MAX_RECORDING_DURATION', 'CLEANUP_AFTER_HOURS']:
                    try:
                        env_value = int(env_value)
                    except ValueError:
                        pass
                self._set_nested_value(config, config_path, env_value)
        
        return config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any):
        """Set a nested configuration value using dot notation"""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation"""
        keys = path.split('.')
        current = self._config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any):
        """Set a configuration value using dot notation"""
        self._set_nested_value(self._config, path, value)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section"""
        return self.get(section, {})
    
    def reload(self):
        """Reload configuration from file"""
        self._config = self._load_config()
    
    def save(self, path: Optional[str] = None):
        """Save current configuration to YAML file"""
        save_path = path or self.config_path
        with open(save_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get the full configuration as a dictionary"""
        return self._config.copy()
    
    def validate(self):
        """Validate configuration"""
        errors = []
        warnings = []
        
        # Required configurations
        discord_token = self.get('discord.token')
        if not discord_token:
            errors.append("discord.token is required")
        elif not discord_token.startswith(('Bot ', 'MTI', 'MTE', 'MTk')):
            warnings.append("discord.token format may be incorrect (should start with 'Bot ' or be a valid bot token)")
        
        # Port validation
        port = self.get('web_server.port')
        if not (1024 <= port <= 65535):
            errors.append(f"web_server.port must be between 1024-65535, got {port}")
        
        # Directory validation and creation
        db_path = self.get('database.path')
        recordings_path = self.get('storage.recordings_path')
        
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create database directory '{db_dir}': {e}")
        
        if not os.path.exists(recordings_path):
            try:
                os.makedirs(recordings_path, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create recordings directory '{recordings_path}': {e}")
        
        # Test write permissions
        test_dirs = [(recordings_path, "recordings"), (db_dir, "database") if db_dir else None]
        for dir_path, name in filter(None, test_dirs):
            try:
                test_file = os.path.join(dir_path, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception as e:
                errors.append(f"No write permission for {name} directory '{dir_path}': {e}")
        
        # Audio format validation
        audio_format = self.get('audio.format')
        if audio_format not in ['mp3', 'wav', 'aac']:
            warnings.append(f"audio.format '{audio_format}' may not be supported")
        
        # Duration limits
        max_duration = self.get('audio.max_duration_seconds')
        if max_duration > 14400:  # 4 hours
            warnings.append(f"audio.max_duration_seconds ({max_duration}s) is very long")
        
        # Log level validation
        log_level = self.get('logging.level')
        if log_level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            warnings.append(f"logging.level '{log_level}' is not standard, using INFO")
            self.set('logging.level', 'INFO')
        
        # File size limits
        max_file_size = self.get('storage.max_file_size_mb')
        if max_file_size > 1000:  # 1GB
            warnings.append(f"storage.max_file_size_mb ({max_file_size}MB) is very large")
        
        # Feature validation
        if not self.get('features.slash_commands'):
            warnings.append("Slash commands are disabled - bot may not be fully functional")
        
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
    
    def get_base_url(self) -> str:
        """Get the base URL for the web server, using IP if no domain is configured"""
        # Check if a domain is configured
        domain = self.get('web_server.domain')
        if domain:
            protocol = 'https' if self.get('web_server.ssl.enabled') else 'http'
            return f"{protocol}://{domain}"
        
        # Fall back to IP address
        host = self.get('web_server.host')
        port = self.get('web_server.port')
        
        # If host is 0.0.0.0, try to get the actual IP
        if host == '0.0.0.0':
            try:
                import socket
                # Get local IP address
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(('8.8.8.8', 80))
                    host = s.getsockname()[0]
            except:
                host = 'localhost'
        
        # Standard ports don't need to be shown
        if (port == 80 and not self.get('web_server.ssl.enabled')) or \
           (port == 443 and self.get('web_server.ssl.enabled')):
            return f"http{'s' if self.get('web_server.ssl.enabled') else ''}://{host}"
        else:
            return f"http{'s' if self.get('web_server.ssl.enabled') else ''}://{host}:{port}"

# Global configuration instance
_config_instance = None

def get_config() -> Config:
    """Get the global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance

# For backwards compatibility, create a default instance
Config = get_config()

def setup_logging(config: Config = None):
    """Setup logging configuration from YAML config"""
    if config is None:
        config = get_config()
    
    logging_config = config.get_section('logging')
    
    # Ensure logs directory exists
    log_dir = os.path.dirname(logging_config['file']['path'])
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Setup handlers
    handlers = []
    
    # Console handler
    if logging_config['console']['enabled']:
        console_handler = logging.StreamHandler()
        if logging_config['console']['format'] == 'detailed':
            console_handler.setFormatter(detailed_formatter)
        else:
            console_handler.setFormatter(simple_formatter)
        handlers.append(console_handler)
    
    # File handler for all logs
    if logging_config['file']['enabled']:
        file_handler = logging.FileHandler(logging_config['file']['path'])
        file_handler.setFormatter(detailed_formatter)
        handlers.append(file_handler)
    
    # Error file handler
    if logging_config['error_file']['enabled']:
        error_handler = logging.FileHandler(logging_config['error_file']['path'])
        error_handler.setFormatter(detailed_formatter)
        error_handler.setLevel(logging.ERROR)
        handlers.append(error_handler)
    
    # Setup root logger
    logging.basicConfig(
        level=getattr(logging, logging_config['level'].upper()),
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Set discord.py logging level
    discord_log_level = getattr(logging, logging_config['discord_log_level'].upper())
    logging.getLogger('discord').setLevel(discord_log_level)
    logging.getLogger('discord.gateway').setLevel(discord_log_level)
    logging.getLogger('discord.client').setLevel(discord_log_level)
    logging.getLogger('discord.voice_client').setLevel(discord_log_level)
    
    # Set uvicorn logging level
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging system initialized - Level: {logging_config['level']}")
    logger.info(f"Log file: {logging_config['file']['path']}")
    if logging_config['error_file']['enabled']:
        logger.info(f"Error log file: {logging_config['error_file']['path']}")