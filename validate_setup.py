#!/usr/bin/env python3

import sys
import os
import subprocess
import asyncio
import tempfile
from pathlib import Path

def print_status(message, status="INFO"):
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m", 
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "END": "\033[0m"
    }
    print(f"{colors.get(status, '')}{status}: {message}{colors['END']}")

def test_imports():
    """Test that all required Python packages can be imported"""
    print_status("Testing Python imports...")
    
    required_imports = [
        "discord",
        "aiosqlite", 
        "fastapi",
        "uvicorn",
        "pydub",
        "secrets",
        "asyncio"
    ]
    
    failed_imports = []
    
    for module in required_imports:
        try:
            __import__(module)
            print_status(f"✓ {module}", "SUCCESS")
        except ImportError as e:
            print_status(f"✗ {module}: {e}", "ERROR")
            failed_imports.append(module)
    
    return len(failed_imports) == 0

def test_ffmpeg():
    """Test that FFmpeg is available and working"""
    print_status("Testing FFmpeg availability...")
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print_status(f"✓ {version_line}", "SUCCESS")
            return True
        else:
            print_status("✗ FFmpeg returned non-zero exit code", "ERROR")
            return False
    except subprocess.TimeoutExpired:
        print_status("✗ FFmpeg command timed out", "ERROR")
        return False
    except FileNotFoundError:
        print_status("✗ FFmpeg not found in PATH", "ERROR")
        return False

def test_environment():
    """Test environment configuration"""
    print_status("Testing environment configuration...")
    
    required_vars = [
        "DISCORD_TOKEN",
        "RECORDINGS_PATH", 
        "DATABASE_PATH"
    ]
    
    optional_vars = [
        "FILE_SERVER_HOST",
        "FILE_SERVER_PORT"
    ]
    
    missing_required = []
    
    for var in required_vars:
        if os.getenv(var):
            print_status(f"✓ {var} is set", "SUCCESS")
        else:
            print_status(f"✗ {var} is not set", "ERROR")
            missing_required.append(var)
    
    for var in optional_vars:
        if os.getenv(var):
            print_status(f"✓ {var} is set", "SUCCESS")
        else:
            print_status(f"~ {var} not set (using default)", "WARNING")
    
    return len(missing_required) == 0

async def test_database():
    """Test database initialization"""
    print_status("Testing database initialization...")
    
    try:
        # Import our database module
        sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
        from database import DatabaseManager
        
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            # Initialize database
            db = DatabaseManager(db_path)
            await db.initialize()
            print_status("✓ Database tables created successfully", "SUCCESS")
            
            # Test a simple insert
            recording_id = await db.start_recording(
                guild_id=123,
                channel_id=456, 
                channel_name="test-channel",
                started_by=789,
                started_by_name="test-user"
            )
            print_status("✓ Database insert operation successful", "SUCCESS")
            
            await db.close()
            return True
            
        finally:
            # Clean up temporary database
            if os.path.exists(db_path):
                os.unlink(db_path)
                
    except Exception as e:
        print_status(f"✗ Database test failed: {e}", "ERROR")
        return False

def test_file_permissions():
    """Test that we can create required directories and files"""
    print_status("Testing file system permissions...")
    
    test_dirs = ["./data", "./recordings", "./temp"]
    success = True
    
    for dir_path in test_dirs:
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            
            # Test write permissions
            test_file = Path(dir_path) / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            
            print_status(f"✓ Can create and write to {dir_path}", "SUCCESS")
            
        except Exception as e:
            print_status(f"✗ Cannot write to {dir_path}: {e}", "ERROR")
            success = False
    
    return success

def test_discord_library():
    """Test Discord library basic functionality"""
    print_status("Testing Discord library...")
    
    try:
        import discord
        from discord.ext import commands
        
        # Test that we can create a bot instance
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        bot = commands.Bot(command_prefix='!', intents=intents)
        print_status("✓ Discord bot instance created successfully", "SUCCESS")
        
        # Test voice receiving capability
        if hasattr(discord, 'VoiceClient'):
            print_status("✓ Voice client functionality available", "SUCCESS")
        else:
            print_status("✗ Voice client not available", "ERROR")
            return False
            
        return True
        
    except Exception as e:
        print_status(f"✗ Discord library test failed: {e}", "ERROR")
        return False

async def run_all_tests():
    """Run all validation tests"""
    print_status("=== Discord Voice Scribe Setup Validation ===")
    print()
    
    tests = [
        ("Python Imports", test_imports),
        ("FFmpeg", test_ffmpeg), 
        ("Environment", test_environment),
        ("File Permissions", test_file_permissions),
        ("Discord Library", test_discord_library),
        ("Database", test_database)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print_status(f"✗ {test_name} test crashed: {e}", "ERROR")
            results[test_name] = False
    
    print("\n=== Summary ===")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓" if result else "✗"
        color = "SUCCESS" if result else "ERROR"
        print_status(f"{status} {test_name}", color)
    
    print()
    if passed == total:
        print_status(f"All {total} tests passed! Setup looks good.", "SUCCESS")
        return True
    else:
        print_status(f"{passed}/{total} tests passed. Please fix the failing tests.", "WARNING")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)