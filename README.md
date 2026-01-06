# YouTube 1080p Downloader (Personal)

A minimal Flask app that downloads YouTube videos, merges video + audio with `yt-dlp` + `ffmpeg`, and streams the final file back to you. The UI now fetches real per-video qualities (e.g., 4K/1080p/720p) and lets you pick container (MP4/MKV) and filename before download.

## Features
- Two-step flow: paste URL → fetch available qualities (per video) → pick quality + container → download or copy link.
- Quality selector populated from `yt-dlp` (shows only what that video supports, including 4K when available).
- Choose container (MP4/MKV) and optional custom filename.
- Copyable download link (helpful on mobile devices); links auto-expire after ~30 minutes.
- Recent download history (in-memory, last 15).
- Inline status updates and a download progress bar when the browser provides content length.

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

Then open `http://localhost:5000` (desktop or mobile).

Flow:
1) Paste a YouTube URL and click **Fetch qualities**.
2) Choose one of the returned qualities and a container (MP4/MKV), optionally set a filename.
3) Click **Download** to trigger your browser’s save dialog, or **Copy download link** to share a one-time download link.

## How it works
- `POST /api/formats` uses `yt-dlp` to list available video heights; the UI shows only those.
- `downloader.py` downloads best video <= selected height + best audio, merges via `ffmpeg`, and remuxes to the chosen container.
- `POST /api/download` streams the merged file immediately; temp files are cleaned right after the response.
- `POST /api/link` prepares a download and returns a copyable `/api/link/<token>` that expires in ~30 minutes; the file is deleted when fetched or expired.
- `GET /api/history` returns the recent (in-memory) downloads for the UI.
- The frontend (`static/*`) handles the two-step fetch/download flow, quality/container/filename inputs, copy-link flow, and history rendering.

## Notes
- This app is intended for personal use. Respect YouTube's Terms of Service and local laws.
- If you prefer a different port, set `PORT=8080` (or any number) before running.
