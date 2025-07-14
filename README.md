# Discord Voice Recording Bot

A Discord bot that records multi-user voice conversations, processes them into mixed audio files, and provides secure download links.

## Features

- 🎙️ Multi-user voice recording with individual stream capture
- 🔄 Automatic audio synchronization and mixing
- 📥 Secure download links with JWT authentication
- 🗄️ SQLite database for recording metadata
- 🐳 Docker containerization for easy deployment
- 🛡️ Security-focused file serving with token-based access

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Discord Bot Token
- FFmpeg (included in Docker image)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd discord-voice-scribe
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables:**
   Edit `.env` and set:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `JWT_SECRET`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

4. **Build and run:**
   ```bash
   docker-compose up -d
   ```

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token to your `.env` file
4. Invite the bot to your server with these permissions:
   - `Connect` (voice)
   - `Speak` (voice)
   - `Use Slash Commands`
   - `Send Messages`
   - `Read Message History`

## Commands

### `/ping`
Test bot responsiveness

### `/join`
Join your voice channel and start recording
- Must be in a voice channel
- Only one recording per server at a time

### `/stop`
Stop the current recording
- Only the person who started recording or users with "Manage Messages" permission can stop

### `/recordings [page]`
List all recordings for the current server
- Paginated (10 recordings per page)
- Shows recording ID, channel, duration, file size, participants

### `/download <recording_id>`
Get a secure download link for a specific recording
- Links expire in 1 hour
- Only accessible to users in the same server or who started the recording

### `/status`
Check current recording status
- Shows duration, participants, and other details

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │ Audio Processor │    │   File Server   │
│                 │    │                 │    │                 │
│ - Slash Commands│────│ - Multi-stream  │────│ - JWT Auth      │
│ - Voice Client  │    │ - Synchronization│    │ - Secure URLs   │
│ - Recording Mgmt│    │ - FFmpeg Mixing │    │ - Download Mgmt │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                        ┌─────────────────┐
                        │ SQLite Database │
                        │                 │
                        │ - Recordings    │
                        │ - Metadata      │
                        │ - Download Tokens│
                        └─────────────────┘
```

## Configuration

Environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Discord bot token | Required |
| `JWT_SECRET` | JWT secret for file downloads | Required |
| `DATABASE_PATH` | SQLite database path | `./data/recordings.db` |
| `RECORDINGS_PATH` | Audio files storage path | `./recordings` |
| `WEB_SERVER_HOST` | File server host | `0.0.0.0` |
| `WEB_SERVER_PORT` | File server port | `8000` |
| `AUDIO_QUALITY` | Audio bitrate | `192k` |
| `AUDIO_FORMAT` | Audio format (mp3/wav) | `mp3` |
| `MAX_RECORDING_DURATION` | Max recording length (seconds) | `7200` |
| `CLEANUP_AFTER_HOURS` | Auto-cleanup after hours | `24` |

## Security Features

- 🔐 JWT-based download authentication
- 🛡️ Directory traversal protection
- ⏱️ Time-limited download links
- 🔒 Non-root Docker user
- 🚫 Secure file path validation

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run locally:**
   ```bash
   python bot.py
   ```

### Testing

The bot includes comprehensive error handling and logging. Check `bot.log` for detailed logs.

### Docker Build

```bash
docker build -t discord-voice-scribe .
```

## Deployment

### Vultr VPS Deployment

1. **Create a Vultr VPS** with at least:
   - 2 CPU cores
   - 4GB RAM
   - 50GB SSD storage

2. **Install Docker:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Clone and deploy:**
   ```bash
   git clone <repository-url>
   cd discord-voice-scribe
   cp .env.example .env
   # Edit .env with your configuration
   docker-compose up -d
   ```

4. **Setup reverse proxy (optional):**
   Use nginx or Traefik for SSL termination and better security.

### Production Considerations

- Use a proper domain name and SSL certificate
- Set up log rotation
- Monitor disk space for recordings
- Consider using cloud storage for long-term recording storage
- Set up automated backups for the database

## Troubleshooting

### Common Issues

1. **Bot not responding to commands:**
   - Check Discord token is valid
   - Ensure bot has required permissions
   - Check bot is online in Discord

2. **Recording fails:**
   - Verify Pycord is installed correctly
   - Check FFmpeg is available in container
   - Ensure adequate disk space

3. **Download links not working:**
   - Check JWT_SECRET is set
   - Verify file server is running on correct port
   - Check firewall allows port 8000

### Logs

Check logs with:
```bash
docker-compose logs -f discord-bot
```

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions, please open an issue on the GitHub repository.