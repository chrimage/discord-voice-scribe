# Discord Recording Bot Product Requirements Document (PRD)

## Goals and Background Context

### Goals

* **Core Functionality:** Successfully implement a bot that can reliably join a voice channel, record each speaker, stop on command, and mix the audio into a single downloadable file.
* **Usability:** Ensure the `/join`, `/stop`, and `/recordings` commands are intuitive and function as expected for day-to-day use.
* **Stability:** The bot should operate without significant errors or crashes during typical recording sessions.

### Background Context

Discord voice channels are powerful for real-time communication, but their content is ephemeral. This bot solves the problem of transient discussions by creating a persistent, accessible audio archive. The core problem is the lack of a simple, integrated way to capture and archive important voice conversations within the Discord platform itself.

### Change Log

| Date | Version | Description | Author |
| :--- | :------ | :---------- | :----- |
| 2025-07-14 | 1.0 | Initial PRD creation from Project Brief. | John, PM |

## Requirements

### Functional

* **FR1:** A `/join` slash command must make the bot join the user's current voice channel and begin recording audio.
* **FR2:** The bot must capture a separate, individual audio stream for each user speaking in the voice channel.
* **FR3:** A `/stop` slash command must make the bot stop recording and leave the current voice channel.
* **FR4:** Upon stopping, the bot must automatically mix the separate audio streams into a single, cohesive audio file.
* **FR5:** A `/recordings` slash command must display a list of all previously completed recordings.
* **FR6:** Each item in the recording list must provide a direct download link to its corresponding mixed audio file.

### Non Functional

* **NFR1:** The application must be containerized using Docker and managed via Docker Compose.
* **NFR2:** The application must be deployable and run on a Vultr VPS.
* **NFR3:** The SQLite database and all generated audio files must be stored on the local filesystem of the host VPS.
* **NFR4:** Discord API tokens and other credentials must be handled securely and not exposed in the source code.
* **NFR5:** The audio mixing process for a 1-hour recording with up to 10 participants should complete in a reasonable time frame (e.g., under 5 minutes).

## Technical Assumptions

### Repository Structure: Monorepo

### Service Architecture

* A single monolithic bot application will handle all functionality. The architecture will consist of the main Python bot process, a dependency on an audio mixing library (like FFMpeg), and a simple file-based data persistence layer using SQLite.

### Testing requirements

* Testing will focus on unit tests for individual functions (e.g., command handling, audio mixing logic) and integration tests to ensure the bot interacts correctly with the Discord API. Manual end-to-end testing will be required to validate the complete recording and retrieval flow.

### Additional Technical Assumptions and Requests

* **Language:** Python with `discord.py`
* **Database:** SQLite
* **Hosting:** Vultr VPS
* **Deployment:** Docker / Docker Compose

## Epics

### Epic 1: Foundation & Core Recording Engine

**Goal:** Establish the project foundation and implement the core ability to record a voice channel conversation and save the raw audio files.

#### Story 1.1: Project Setup & Dockerization

As a Bot Operator, I want the project to have a complete, containerized setup, so that I can easily build and run the bot in a consistent environment.

##### Acceptance Criteria

1.  A `Dockerfile` is created for the Python application.
2.  A `docker-compose.yml` file is created to manage the bot service.
3.  The project includes a `requirements.txt` file listing all Python dependencies, including `discord.py`.
4.  The bot can be successfully built and started using `docker-compose up`.

#### Story 1.2: Basic Bot Connection & Command Handling

As a Discord User, I want the bot to connect to my server and respond to a basic command, so that I can verify it's online and operational.

##### Acceptance Criteria

1.  The bot successfully connects to a Discord server using a secure token.
2.  A `/ping` command is implemented.
3.  When a user types `/ping`, the bot responds with "Pong!".

#### Story 1.3: Implement Join & Record Functionality

As a Discord User, I want to use a `/join` command to make the bot enter my voice channel and start recording everyone, so that I can capture a conversation.

##### Acceptance Criteria

1.  A `/join` command is implemented.
2.  When executed, the bot joins the voice channel of the user who issued the command.
3.  Upon joining, the bot begins listening and recording audio.
4.  The bot saves a separate, raw audio file for each user who speaks.
5.  The raw audio files are saved to a designated local directory.

#### Story 1.4: Implement Stop & Disconnect Functionality

As a Discord User, I want to use a `/stop` command to end the recording session, so that the bot saves the final raw audio and leaves the channel.

##### Acceptance Criteria

1.  A `/stop` command is implemented.
2.  When executed, the bot stops listening for audio in the voice channel.
3.  The bot finalizes and saves all raw audio files.
4.  The bot disconnects from the voice channel.

### Epic 2: Audio Processing & Retrieval

**Goal:** Process the raw recorded audio, store metadata, and provide a way for users to access the final, mixed recordings.

#### Story 2.1: Implement Audio Mixing Service

As a Bot Operator, I want the raw audio files from a session to be automatically mixed into a single file, so that a coherent recording is created.

##### Acceptance Criteria

1.  An audio processing function is created that triggers after a recording is stopped.
2.  The function takes all raw audio files from a single session as input.
3.  The function uses an audio library (e.g., FFMpeg) to merge the files into one master audio file (e.g., in `.mp3` or `.wav` format).
4.  The final mixed file is saved to a designated local directory.
5.  The original raw audio files are deleted after a successful mix.

#### Story 2.2: Implement Database for Recording Metadata

As a Bot Operator, I want the details of each recording to be saved in a database, so that I have a persistent log of all conversations.

##### Acceptance Criteria

1.  An SQLite database is initialized with a `recordings` table.
2.  The table includes columns for ID, channel name, date, duration, and the file path to the final mixed audio file.
3.  After a recording is successfully mixed, a new entry is created in the `recordings` table with the correct metadata.

#### Story 2.3: Implement Recordings List Command

As a Discord User, I want a `/recordings` command, so that I can see a list of all available recordings.

##### Acceptance Criteria

1.  A `/recordings` command is implemented.
2.  When executed, the bot queries the SQLite database for all recordings.
3.  The bot formats the list and displays it to the user in a readable format (e.g., an embed).
4.  The list includes the channel, date, and duration for each recording.
5.  If the list is long, it is paginated to not spam the channel.

#### Story 2.4: Provide Download Links for Recordings

As a Discord User, I want to receive a download link for a recording, so that I can save it to my computer.

##### Acceptance Criteria

1.  The `/recordings` command output now includes a unique identifier for each recording.
2.  A `/get_recording [ID]` command is implemented.
3.  When a user provides a valid recording ID, the bot provides a direct, temporary download link to the audio file.
4.  (Alternative to #2 and #3) The `/recordings` command itself provides the direct download link for each recording.

## Checklist Results Report

*This PRD has been generated in YOLO mode. A thorough validation against the `pm-checklist` is recommended before handing off to the architect.*

## Next Steps

### Architect Prompt

Based on this PRD, please design a technical architecture that can handle the specified requirements. Pay special attention to the audio processing pipeline, the local file and database management within a Docker container, and the method for serving downloadable audio files.
