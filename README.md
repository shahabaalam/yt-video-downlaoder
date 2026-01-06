# Personal YouTube Downloader (FastAPI + yt-dlp)

Private, personal-use web app to download YouTube videos via yt-dlp. Targets MP4 (1080p/720p) or MP3 audio, merges audio/video with ffmpeg, auto-cleans files older than 1 hour, and prevents concurrent downloads per client.

## Features
- FastAPI backend serving static HTML/CSS/JS
- Quality options: 1080p (137+best audio), 720p, audio-only (MP3)
- Progress/status polling with merged output download link
- Auto-delete downloads older than 1 hour
- Single active download per client to reduce load
- Render-ready: persistent disk mount, start/build commands, ffmpeg install

## Quickstart (local)
Requirements: Python 3.11+ (Pydantic v2 compatible), ffmpeg installed, `pip`.

```bash
python -m venv .venv
.\.venv\Scripts\activate  # on Windows PowerShell
# source .venv/bin/activate  # on macOS/Linux
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and use the form.

## Render Deployment
1. Create a Web Service from this repo.
2. Add a Persistent Disk (e.g., name `downloads`, mount path `/data`, size 5GB).
3. Render uses `render.yaml` to install ffmpeg, dependencies, and start via uvicorn.

## Environment
- `DOWNLOAD_DIR` (optional): custom download directory. Defaults to `/data/downloads` (for Render persistent disk).

## Project Structure
- `app/main.py` — FastAPI app, download logic, cleanup, file serving
- `static/` — HTML, CSS, JS frontend
- `render.yaml` — Render service definition with ffmpeg install and start command
- `requirements.txt` — Python dependencies

## Notes
- For personal/private use only. No monetization or public scraping logic included.
