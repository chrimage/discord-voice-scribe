import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List

from bot import bot
from config import Config

logger = logging.getLogger(__name__)

class RecordingSink(discord.sinks.WaveSink):
    """Custom recording sink for multi-user audio capture"""
    
    def __init__(self, recording_id: int):
        super().__init__()
        self.recording_id = recording_id
        self.temp_dir = tempfile.mkdtemp(prefix=f"recording_{recording_id}_")
        self.user_files = {}
        logger.info(f"Created recording sink for recording {recording_id}")
    
    def write(self, data, user):
        """Write audio data for a specific user"""
        if user is None:
            return
        
        # Create file for user if not exists
        if user.id not in self.user_files:
            file_path = os.path.join(self.temp_dir, f"user_{user.id}.wav")
            self.user_files[user.id] = {
                'file': open(file_path, 'wb'),
                'path': file_path,
                'user': user
            }
            logger.info(f"Started recording for user {user.display_name} (ID: {user.id})")
        
        # Write audio data
        self.user_files[user.id]['file'].write(data)
    
    def cleanup(self):
        """Clean up recording files"""
        user_audio_files = {}
        
        for user_id, file_info in self.user_files.items():
            file_info['file'].close()
            
            # Check if file has content
            if os.path.getsize(file_info['path']) > 0:
                user_audio_files[str(user_id)] = file_info['path']
            else:
                # Remove empty files
                try:
                    os.remove(file_info['path'])
                except:
                    pass
        
        logger.info(f"Recording cleanup complete. Valid files: {len(user_audio_files)}")
        return user_audio_files

@bot.tree.command(name="ping", description="Test bot responsiveness")
async def ping(interaction: discord.Interaction):
    """Test command to check bot responsiveness"""
    await interaction.response.send_message(
        f"Pong! Latency: {round(bot.latency * 1000)}ms", 
        ephemeral=True
    )

@bot.tree.command(name="join", description="Join your voice channel and start recording")
async def join_command(interaction: discord.Interaction):
    """Join user's voice channel and start recording"""
    await interaction.response.defer()
    
    # Check if user is in a voice channel
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send(
            "❌ You need to be in a voice channel to start recording!",
            ephemeral=True
        )
        return
    
    guild_id = interaction.guild.id
    
    # Check if already recording in this guild
    if guild_id in bot.active_recordings:
        active_recording = bot.active_recordings[guild_id]
        embed = discord.Embed(
            title="Already Recording",
            description=f"Already recording in <#{active_recording['channel_id']}>",
            color=discord.Color.orange()
        )
        embed.add_field(name="Recording ID", value=active_recording['recording_id'], inline=True)
        embed.add_field(name="Started by", value=f"<@{active_recording['started_by']}>", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    try:
        # Start recording in database
        recording_id = await bot.db.start_recording(
            guild_id=guild_id,
            channel_id=interaction.user.voice.channel.id,
            channel_name=interaction.user.voice.channel.name,
            started_by=interaction.user.id,
            started_by_name=interaction.user.display_name
        )
        
        # Connect to voice channel
        voice_client = await interaction.user.voice.channel.connect()
        
        # Create recording sink
        sink = RecordingSink(recording_id)
        
        # Start recording
        voice_client.start_recording(sink, lambda s, c: asyncio.create_task(recording_finished(s, c, recording_id)))
        
        # Store recording info
        participants = [member.display_name for member in voice_client.channel.members if not member.bot]
        bot.active_recordings[guild_id] = {
            'recording_id': recording_id,
            'voice_client': voice_client,
            'sink': sink,
            'channel_id': interaction.user.voice.channel.id,
            'started_by': interaction.user.id,
            'start_time': datetime.utcnow(),
            'participants': participants,
            'channel': interaction.channel
        }
        
        # Send confirmation
        embed = discord.Embed(
            title="🎙️ Recording Started",
            description=f"Recording conversation in **{interaction.user.voice.channel.name}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Recording ID", value=recording_id, inline=True)
        embed.add_field(name="Participants", value=", ".join(participants) if participants else "None", inline=True)
        embed.add_field(name="Started by", value=interaction.user.display_name, inline=True)
        embed.add_field(name="Stop Recording", value="Use `/stop` to end recording", inline=False)
        
        await interaction.followup.send(embed=embed)
        logger.info(f"Started recording {recording_id} in guild {guild_id}")
        
    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        await interaction.followup.send(
            "❌ Failed to start recording. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="stop", description="Stop the current recording")
async def stop_command(interaction: discord.Interaction):
    """Stop the current recording"""
    await interaction.response.defer()
    
    guild_id = interaction.guild.id
    
    # Check if recording in this guild
    if guild_id not in bot.active_recordings:
        await interaction.followup.send(
            "❌ No active recording in this server.",
            ephemeral=True
        )
        return
    
    recording_info = bot.active_recordings[guild_id]
    recording_id = recording_info['recording_id']
    
    # Check if user can stop recording (started by them or has manage messages permission)
    if (interaction.user.id != recording_info['started_by'] and 
        not interaction.user.guild_permissions.manage_messages):
        await interaction.followup.send(
            "❌ You can only stop recordings you started, or you need 'Manage Messages' permission.",
            ephemeral=True
        )
        return
    
    try:
        # Send immediate response
        embed = discord.Embed(
            title="🛑 Stopping Recording",
            description=f"Recording #{recording_id} is being stopped and processed...",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed)
        
        # Stop recording
        await bot.stop_recording(guild_id)
        
        logger.info(f"Stopped recording {recording_id} in guild {guild_id}")
        
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        await interaction.followup.send(
            "❌ Failed to stop recording. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="recordings", description="List all recordings for this server")
async def recordings_command(interaction: discord.Interaction, page: int = 1):
    """List recordings for the current server"""
    await interaction.response.defer()
    
    guild_id = interaction.guild.id
    limit = 10
    offset = (page - 1) * limit
    
    try:
        # Get recordings from database
        recordings = await bot.db.get_guild_recordings(guild_id, limit, offset)
        
        if not recordings:
            embed = discord.Embed(
                title="📼 No Recordings",
                description="No recordings found for this server.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create embed
        embed = discord.Embed(
            title="📼 Server Recordings",
            description=f"Page {page} • Showing {len(recordings)} recordings",
            color=discord.Color.blue()
        )
        
        for recording in recordings:
            status_emoji = "✅" if recording['status'] == 'completed' else "🔄"
            
            # Format duration
            duration = recording['duration'] if recording['duration'] else 0
            duration_str = f"{duration // 60}:{duration % 60:02d}"
            
            # Format file size
            file_size = recording['file_size'] if recording['file_size'] else 0
            file_size_str = f"{file_size / (1024*1024):.1f} MB" if file_size > 0 else "N/A"
            
            # Format participants
            participants = recording['participants'] if recording['participants'] else []
            participants_str = ", ".join(participants) if participants else "None"
            
            embed.add_field(
                name=f"{status_emoji} Recording #{recording['id']}",
                value=f"**Channel:** {recording['channel_name']}\n"
                      f"**Started by:** {recording['started_by_name']}\n"
                      f"**Duration:** {duration_str}\n"
                      f"**Size:** {file_size_str}\n"
                      f"**Participants:** {participants_str}\n"
                      f"**Date:** {recording['start_time'][:10]}",
                inline=False
            )
        
        # Add download instructions
        embed.add_field(
            name="📥 How to Download",
            value="Use `/download <recording_id>` to get a download link for a specific recording.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error listing recordings: {e}")
        await interaction.followup.send(
            "❌ Failed to list recordings. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="download", description="Get download link for a recording")
async def download_command(interaction: discord.Interaction, recording_id: int):
    """Get download link for a specific recording"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get recording from database
        recording = await bot.db.get_recording(recording_id)
        
        if not recording:
            await interaction.followup.send(
                "❌ Recording not found.",
                ephemeral=True
            )
            return
        
        # Check if user can access this recording (same guild or started by them)
        if (recording['guild_id'] != interaction.guild.id and 
            recording['started_by'] != interaction.user.id):
            await interaction.followup.send(
                "❌ You don't have permission to download this recording.",
                ephemeral=True
            )
            return
        
        # Check if recording is completed
        if recording['status'] != 'completed':
            await interaction.followup.send(
                "❌ Recording is not yet completed. Please wait for processing to finish.",
                ephemeral=True
            )
            return
        
        # Check if file exists
        if not recording['file_path'] or not os.path.exists(recording['file_path']):
            await interaction.followup.send(
                "❌ Recording file not found. It may have been deleted.",
                ephemeral=True
            )
            return
        
        # Generate download token
        token = bot.file_server.generate_download_token(
            recording_id=recording_id,
            file_path=recording['file_path'],
            user_id=interaction.user.id,
            expires_hours=1
        )
        
        # Store token in database
        expires_at = datetime.utcnow() + timedelta(hours=1)
        await bot.db.create_download_token(token, recording_id, interaction.user.id, expires_at)
        
        # Generate download URL
        download_url = bot.file_server.get_download_url(
            token,
            f"http://localhost:{Config.WEB_SERVER_PORT}"  # In production, use actual domain
        )
        
        # Create embed
        embed = discord.Embed(
            title="📥 Download Link",
            description=f"Download link for Recording #{recording_id}",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Download URL", value=download_url, inline=False)
        embed.add_field(name="Expires", value="1 hour", inline=True)
        embed.add_field(name="File Size", value=f"{recording['file_size'] / (1024*1024):.1f} MB", inline=True)
        embed.add_field(name="Duration", value=f"{recording['duration'] // 60}:{recording['duration'] % 60:02d}", inline=True)
        
        embed.set_footer(text="⚠️ This link will expire in 1 hour and can only be used once.")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error generating download link: {e}")
        await interaction.followup.send(
            "❌ Failed to generate download link. Please try again.",
            ephemeral=True
        )

async def recording_finished(sink, channel, recording_id):
    """Callback when recording is finished"""
    try:
        # Get user audio files
        user_audio_files = sink.cleanup()
        
        # Find the recording info
        recording_info = None
        for guild_id, info in bot.active_recordings.items():
            if info['recording_id'] == recording_id:
                recording_info = info
                break
        
        if recording_info:
            recording_info['user_audio_files'] = user_audio_files
            logger.info(f"Recording {recording_id} finished, starting processing")
        
    except Exception as e:
        logger.error(f"Error in recording finished callback: {e}")

@bot.tree.command(name="status", description="Check current recording status")
async def status_command(interaction: discord.Interaction):
    """Check the current recording status"""
    await interaction.response.defer(ephemeral=True)
    
    guild_id = interaction.guild.id
    
    # Check if recording in this guild
    if guild_id not in bot.active_recordings:
        await interaction.followup.send(
            "ℹ️ No active recording in this server.",
            ephemeral=True
        )
        return
    
    recording_info = bot.active_recordings[guild_id]
    recording_id = recording_info['recording_id']
    
    # Calculate duration
    duration = (datetime.utcnow() - recording_info['start_time']).total_seconds()
    duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
    
    # Get current participants
    voice_client = recording_info['voice_client']
    current_participants = []
    if voice_client and voice_client.channel:
        current_participants = [member.display_name for member in voice_client.channel.members if not member.bot]
    
    embed = discord.Embed(
        title="🎙️ Recording Status",
        description=f"Recording #{recording_id} is currently active",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.add_field(name="Channel", value=f"<#{recording_info['channel_id']}>", inline=True)
    embed.add_field(name="Started by", value=f"<@{recording_info['started_by']}>", inline=True)
    embed.add_field(name="Current Participants", value=", ".join(current_participants) if current_participants else "None", inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)