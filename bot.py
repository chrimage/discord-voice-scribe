import discord
from discord.ext import commands, tasks
import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

from config import get_config, setup_logging
from database import DatabaseManager
from audio_processor import AudioProcessor
from file_server import FileServer

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

class VoiceRecordingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        
        # Configuration
        self.config = get_config()
        self.config.validate()
        
        # Core components
        self.db = DatabaseManager(self.config.DATABASE_PATH)
        self.audio_processor = AudioProcessor(
            self.config.RECORDINGS_PATH, 
            self.config.AUDIO_QUALITY, 
            self.config.AUDIO_FORMAT
        )
        self.file_server = FileServer(self.config.RECORDINGS_PATH)
        
        # Recording state
        self.active_recordings: Dict[int, Dict] = {}  # guild_id -> recording_info
        self.recording_tasks: Dict[int, asyncio.Task] = {}  # guild_id -> processing_task
        
        # Ensure recordings directory exists
        os.makedirs(self.config.RECORDINGS_PATH, exist_ok=True)
    
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        logger.info("Setting up bot...")
        
        try:
            # Initialize database
            await self.db.initialize()
            logger.info("Database initialization successful")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise RuntimeError("Failed to initialize database") from e
        
        try:
            # Start file server
            await self.file_server.start(self.config.WEB_SERVER_HOST, self.config.WEB_SERVER_PORT)
            logger.info("File server started successfully")
        except Exception as e:
            logger.error(f"File server startup failed: {e}")
            raise RuntimeError("Failed to start file server") from e
        
        try:
            # Start cleanup task
            self.cleanup_task.start()
            logger.info("Cleanup task started successfully")
        except Exception as e:
            logger.error(f"Cleanup task startup failed: {e}")
            # Don't fail setup for cleanup task
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            # Don't fail setup for command sync issues
        
        logger.info("Bot setup complete")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        activity_config = self.config.get('discord.activity')
        activity_type = getattr(discord.ActivityType, activity_config['type'], discord.ActivityType.listening)
        await self.change_presence(
            activity=discord.Activity(
                type=activity_type,
                name=activity_config['name']
            )
        )
    
    async def on_guild_join(self, guild):
        """Called when bot joins a guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        
        # Clean up any active recordings for this guild
        if guild.id in self.active_recordings:
            await self.stop_recording(guild.id)
    
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        guild_id = member.guild.id
        
        # Check if we're recording in this guild
        if guild_id not in self.active_recordings:
            return
        
        recording_info = self.active_recordings[guild_id]
        
        # If the bot was disconnected, stop recording
        if member == self.user and after.channel is None:
            logger.warning(f"Bot disconnected from voice channel in guild {guild_id}")
            await self.stop_recording(guild_id)
            return
        
        # Update participant list if someone joins/leaves the recorded channel
        if recording_info['voice_client'] and recording_info['voice_client'].channel:
            if before.channel == recording_info['voice_client'].channel or after.channel == recording_info['voice_client'].channel:
                await self.update_recording_participants(guild_id)
    
    async def update_recording_participants(self, guild_id: int):
        """Update the participant list for an active recording"""
        if guild_id not in self.active_recordings:
            return
        
        recording_info = self.active_recordings[guild_id]
        voice_client = recording_info['voice_client']
        
        if voice_client and voice_client.channel:
            participants = [member.display_name for member in voice_client.channel.members if not member.bot]
            recording_info['participants'] = participants
            logger.info(f"Updated participants for recording {recording_info['recording_id']}: {participants}")
    
    async def stop_recording(self, guild_id: int):
        """Stop recording for a guild"""
        if guild_id not in self.active_recordings:
            return
        
        recording_info = self.active_recordings[guild_id]
        recording_id = recording_info['recording_id']
        
        logger.info(f"Stopping recording {recording_id} for guild {guild_id}")
        
        try:
            # Stop voice client
            voice_client = recording_info.get('voice_client')
            if voice_client:
                voice_client.stop_recording()
                await voice_client.disconnect()
            
            # Cancel any ongoing processing
            if guild_id in self.recording_tasks:
                self.recording_tasks[guild_id].cancel()
                del self.recording_tasks[guild_id]
            
            # Process the recording
            await self.process_recording(recording_info)
            
        except Exception as e:
            logger.error(f"Error stopping recording {recording_id}: {e}")
        finally:
            # Clean up
            if guild_id in self.active_recordings:
                del self.active_recordings[guild_id]
    
    async def process_recording(self, recording_info: Dict):
        """Process a completed recording"""
        recording_id = recording_info['recording_id']
        
        try:
            # Get user audio files from the sink
            user_audio_files = recording_info.get('user_audio_files', {})
            
            if not user_audio_files:
                logger.warning(f"No audio files found for recording {recording_id}")
                return
            
            # Process audio
            participants = recording_info.get('participants', [])
            file_path, file_size = await self.audio_processor.process_recording(
                user_audio_files, recording_id, participants
            )
            
            # Calculate duration
            start_time = recording_info['start_time']
            duration = int((datetime.utcnow() - start_time).total_seconds())
            
            # Update database
            await self.db.finish_recording(
                recording_id, file_path, file_size, participants, duration
            )
            
            # Notify the user
            channel = recording_info.get('channel')
            if channel:
                embed = discord.Embed(
                    title="Recording Complete",
                    description=f"Recording #{recording_id} has been processed successfully!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02d}", inline=True)
                embed.add_field(name="Participants", value=", ".join(participants) if participants else "None", inline=True)
                embed.add_field(name="File Size", value=f"{file_size / (1024*1024):.1f} MB", inline=True)
                embed.add_field(name="Download", value="Use `/recordings` to get download link", inline=False)
                
                await channel.send(embed=embed)
                logger.info(f"Recording {recording_id} completed and user notified")
            
        except Exception as e:
            logger.error(f"Error processing recording {recording_id}: {e}")
            
            # Notify user of error
            channel = recording_info.get('channel')
            if channel:
                embed = discord.Embed(
                    title="Recording Error",
                    description=f"Failed to process recording #{recording_id}. Please try again.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
    
    @tasks.loop(hours=1)
    async def cleanup_task(self):
        """Periodic cleanup task"""
        try:
            # Clean up expired download tokens from database
            await self.db.cleanup_expired_tokens()
            
            # Clean up expired tokens from file server memory
            expired_count = self.file_server.cleanup_expired_tokens()
            
            # Clean up temporary files
            self.audio_processor.cleanup_temp_files()
            
            logger.info(f"Cleanup task completed. Cleaned {expired_count} expired tokens.")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
    
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down bot...")
        
        # Stop all active recordings
        for guild_id in list(self.active_recordings.keys()):
            await self.stop_recording(guild_id)
        
        # Cancel cleanup task
        if hasattr(self, 'cleanup_task'):
            self.cleanup_task.cancel()
        
        # Close components
        await self.file_server.stop()
        await self.db.close()
        
        # Call parent close
        await super().close()
        
        logger.info("Bot shutdown complete")

# Create bot instance
bot = VoiceRecordingBot()

# Import and register commands
from commands import *

if __name__ == "__main__":
    try:
        logger.info("Starting Discord Voice Recording Bot...")
        config = get_config()
        bot.run(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except discord.LoginFailure as e:
        logger.error(f"Discord login failed - check your DISCORD_TOKEN: {e}")
        exit(1)
    except discord.HTTPException as e:
        logger.error(f"Discord HTTP error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Bot crashed with unexpected error: {e}", exc_info=True)
        exit(1)