import asyncio
import subprocess
import os
import logging
from typing import List, Dict, Tuple
import tempfile
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Audio processing utilities for mixing and synchronization"""
    
    def __init__(self, recordings_path: str, audio_quality: str = '192k', audio_format: str = 'mp3'):
        self.recordings_path = Path(recordings_path)
        self.audio_quality = audio_quality
        self.audio_format = audio_format
        self.temp_dir = Path(tempfile.gettempdir()) / 'discord-voice-scribe'
        self.temp_dir.mkdir(exist_ok=True)
    
    async def process_recording(self, user_audio_files: Dict[str, str], 
                              recording_id: int, participants: List[str]) -> Tuple[str, int]:
        """
        Process individual user audio files into a single mixed recording
        
        Args:
            user_audio_files: Dictionary mapping user_id to file path
            recording_id: Recording ID for naming
            participants: List of participant names
            
        Returns:
            Tuple of (final_file_path, file_size_bytes)
        """
        if not user_audio_files:
            raise ValueError("No audio files to process")
        
        logger.info(f"Processing recording {recording_id} with {len(user_audio_files)} participants")
        
        try:
            # Create temporary directory for processing
            temp_recording_dir = self.temp_dir / f"recording_{recording_id}"
            temp_recording_dir.mkdir(exist_ok=True)
            
            # Convert raw audio files to WAV format with consistent properties
            normalized_files = []
            max_duration = 0
            
            for user_id, file_path in user_audio_files.items():
                if not os.path.exists(file_path):
                    logger.warning(f"Audio file not found: {file_path}")
                    continue
                
                # Convert to WAV with consistent sample rate and format
                normalized_path = temp_recording_dir / f"user_{user_id}_normalized.wav"
                
                # Get audio duration for synchronization
                duration = await self._get_audio_duration(file_path)
                max_duration = max(max_duration, duration)
                
                # Normalize audio file
                await self._normalize_audio_file(file_path, normalized_path)
                normalized_files.append(normalized_path)
            
            if not normalized_files:
                raise ValueError("No valid audio files found")
            
            # Synchronize audio files (pad to same length)
            synchronized_files = []
            for file_path in normalized_files:
                sync_path = temp_recording_dir / f"sync_{file_path.name}"
                await self._synchronize_audio_file(file_path, sync_path, max_duration)
                synchronized_files.append(sync_path)
            
            # Mix all synchronized files
            final_file_path = self.recordings_path / f"recording_{recording_id}.{self.audio_format}"
            await self._mix_audio_files(synchronized_files, final_file_path)
            
            # Get file size
            file_size = os.path.getsize(final_file_path)
            
            # Cleanup temporary files
            shutil.rmtree(temp_recording_dir, ignore_errors=True)
            
            logger.info(f"Recording {recording_id} processed successfully: {final_file_path} ({file_size} bytes)")
            return str(final_file_path), file_size
            
        except Exception as e:
            logger.error(f"Error processing recording {recording_id}: {e}")
            # Cleanup on error
            if 'temp_recording_dir' in locals():
                shutil.rmtree(temp_recording_dir, ignore_errors=True)
            raise
    
    async def _get_audio_duration(self, file_path: str) -> float:
        """Get audio duration in seconds using FFprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', file_path
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"FFprobe error: {stderr.decode()}")
                return 0.0
            
            import json
            data = json.loads(stdout.decode())
            return float(data['format']['duration'])
            
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0.0
    
    async def _normalize_audio_file(self, input_path: str, output_path: Path):
        """Normalize audio file to consistent format"""
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', '48000',  # 48kHz sample rate (Discord standard)
            '-ac', '2',      # Stereo
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=60  # 60 second timeout
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg normalization failed for {input_path}: {error_msg}")
                raise RuntimeError(f"Audio normalization failed: {error_msg}")
                
        except asyncio.TimeoutError:
            logger.error(f"FFmpeg normalization timed out for {input_path}")
            raise RuntimeError("Audio normalization timed out")
        except FileNotFoundError:
            logger.error("FFmpeg not found - ensure FFmpeg is installed")
            raise RuntimeError("FFmpeg not found - please install FFmpeg")
    
    async def _synchronize_audio_file(self, input_path: Path, output_path: Path, target_duration: float):
        """Synchronize audio file to target duration by padding with silence"""
        current_duration = await self._get_audio_duration(str(input_path))
        
        if current_duration >= target_duration:
            # File is already long enough, just copy
            shutil.copy2(input_path, output_path)
            return
        
        # Pad with silence to match target duration
        silence_duration = target_duration - current_duration
        
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=48000:duration={silence_duration}',
            '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]',
            '-map', '[out]',
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
            raise RuntimeError(f"Audio synchronization failed: {error_msg}")
    
    async def _mix_audio_files(self, input_files: List[Path], output_path: Path):
        """Mix multiple audio files into one using FFmpeg"""
        if len(input_files) == 1:
            # Single file, just convert to final format
            cmd = [
                'ffmpeg', '-i', str(input_files[0]),
                '-acodec', 'libmp3lame' if self.audio_format == 'mp3' else 'aac',
                '-b:a', self.audio_quality,
                '-y',  # Overwrite output file
                str(output_path)
            ]
        else:
            # Multiple files, mix them
            inputs = []
            for file_path in input_files:
                inputs.extend(['-i', str(file_path)])
            
            # Create filter complex for mixing
            filter_inputs = ''.join([f'[{i}:a]' for i in range(len(input_files))])
            filter_complex = f'{filter_inputs}amix=inputs={len(input_files)}:duration=longest:dropout_transition=0[out]'
            
            cmd = [
                'ffmpeg',
                *inputs,
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-acodec', 'libmp3lame' if self.audio_format == 'mp3' else 'aac',
                '-b:a', self.audio_quality,
                '-y',  # Overwrite output file
                str(output_path)
            ]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
            raise RuntimeError(f"Audio mixing failed: {error_msg}")
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info("Temporary files cleaned up")