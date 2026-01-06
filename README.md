# YouTube 1080p Downloader (Personal)

A minimal Flask app that downloads YouTube videos (1080p/720p/480p or audio-only), merges video + audio with `yt-dlp` + `ffmpeg`, and streams the final file back to you. Includes a mobile-friendly single-page frontend.

## Features
- Quality selector: 1080p / 720p / 480p / audio-only.
- Optional custom filename for the downloaded file.
- Copyable download link (helpful on mobile devices); links auto-expire after ~30 minutes.
- Recent download history (in-memory, last 15).
- Inline status updates for start/completed/error.

## Requirements
- Python 3.9+ (tested with 3.11)
- `ffmpeg` available on your `PATH`
- Python packages: `Flask`, `yt-dlp` (see `requirements.txt`)

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the server
```bash
python app.py
# Server listens on http://0.0.0.0:5000
```

Then open `http://localhost:5000` (desktop or mobile). Paste a YouTube URL, choose quality (or audio-only), set an optional filename, and click **Download**. Use **Copy download link** if you want a sharable link instead of an immediate file save.

## How it works
- `downloader.py` contains the download/merge logic using `yt-dlp` with quality presets and `ffmpeg` post-processing.
- `POST /api/download` streams the merged file immediately; temp files are cleaned right after the response.
- `POST /api/link` prepares a download and returns a copyable `/api/link/<token>` that expires in ~30 minutes; the file is deleted when fetched or expired.
- `GET /api/history` returns the recent (in-memory) downloads for the UI.
- The frontend (`static/*`) handles the form, quality/filename inputs, copy-link flow, and history rendering.

## Notes
- This app is intended for personal use. Respect YouTube's Terms of Service and local laws.
- If you prefer a different port, set `PORT=8080` (or any number) before running.
