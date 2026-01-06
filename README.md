# YouTube 1080p Downloader (Personal)

A minimal Flask app that downloads YouTube videos up to 1080p, merges video + audio with `yt-dlp` + `ffmpeg`, and streams the final MP4 back to you. Includes a mobile-friendly single-page frontend.

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

Then open `http://localhost:5000` (desktop or mobile). Paste a YouTube URL and click **Download MP4**; the backend fetches the best 1080p stream + best audio, merges them, and serves the combined file as an attachment.

## How it works
- `downloader.py` contains the download/merge logic using `yt-dlp` with a 1080p cap and `merge_output_format=mp4`.
- Temporary files are created per request and cleaned up after the response is sent.
- The frontend (`static/index.html`) calls `POST /api/download` with JSON `{ "url": "<youtube link>" }` and then saves the returned blob locally.

## Notes
- This app is intended for personal use. Respect YouTube's Terms of Service and local laws.
- If you prefer a different port, set `PORT=8080` (or any number) before running.
