# YTGrab (YouTube downloader)

A Flask + yt-dlp + FFmpeg app that downloads YouTube video or audio. The UI shows real per-video qualities, handles playlists automatically (returns ZIPs), and lets you pick container and filename before downloading.

## Features
- Video + audio combined: paste URL, fetch real qualities, pick quality/container, download.
- Automatic playlist detection: playlist URLs are zipped (video: MP4/MKV; audio: MP3); dedicated page at `playlist.html`.
- Quality selector populated from `yt-dlp` (only what the video supports, including 4K when present).
- Choose container (MP4/MKV) and optional custom filename.
- Copyable download link (auto-expires ~30 minutes).
- Recent download history (in-memory, last 15).
- Inline status updates and a progress bar when content length is known.

## Requirements
- Python 3.9+
- `ffmpeg` on your `PATH`
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
# Listens on http://0.0.0.0:5000 (set PORT to override)
```

Then open `http://localhost:5000`:
- `index.html`: single video or auto-detected playlist; pick Audio/Video and download.
- `playlist.html`: playlist-focused page (video or audio ZIP).
- `how.html`: usage tips.

Flow:
1) Paste a YouTube URL and click **Fetch formats**.
2) Pick a row (Audio or Video). Playlist URLs are handled automatically and returned as a ZIP.
3) Click **Download**; history tracks your last 15 downloads.

## Notes
- For the best format detection, install a JS runtime (Node.js or Deno) so yt-dlp can resolve all formats. Without it, some formats may be missing.
- This app is intended for personal use. Respect YouTube’s Terms of Service and local laws.
- Deploying to Vercel (no apt): place a static ffmpeg binary at `bin/ffmpeg` (Linux x64 build), and the app will auto-use it via `FFMPEG_BINARY`. Keep the binary lean to fit size limits.
