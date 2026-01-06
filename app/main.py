import asyncio
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_DIR", "/data/downloads")).resolve()
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_FILE_AGE = timedelta(hours=1)
CLEANUP_INTERVAL = 300  # seconds

app = FastAPI(title="Personal YouTube Downloader", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@dataclass
class DownloadJob:
    job_id: str
    url: str
    quality: str
    status: str = "queued"
    progress: float = 0.0
    filename: Optional[str] = None
    filepath: Optional[Path] = None
    error: Optional[str] = None
    owner: str = "anonymous"
    created_at: datetime = field(default_factory=datetime.utcnow)


class DownloadPayload(BaseModel):
    url: str
    quality: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return cleaned

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        allowed = {"1080p", "720p", "audio"}
        if v not in allowed:
            raise ValueError(f"Quality must be one of: {', '.join(sorted(allowed))}")
        return v


jobs: Dict[str, DownloadJob] = {}
client_active: Dict[str, str] = {}
lock = threading.Lock()
cleanup_task: Optional[asyncio.Task] = None


def ensure_directories() -> None:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def get_client_id(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host or "anonymous"


def build_format_options(job: DownloadJob) -> Dict:
    format_map = {
        "1080p": "137+bestaudio/bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]",
        "720p": "22/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
        "audio": "bestaudio[ext=m4a]/bestaudio",
    }
    if job.quality == "audio":
        postprocessors = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        postprocessors = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

    return {
        "format": format_map[job.quality],
        "outtmpl": str(DOWNLOAD_ROOT / f"{job.job_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [lambda d: progress_hook(job.job_id, d)],
        "postprocessors": postprocessors,
    }


def progress_hook(job_id: str, data: Dict) -> None:
    with lock:
        job = jobs.get(job_id)
        if not job:
            return
        if data.get("status") == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total > 0:
                job.progress = round(min(100.0, (downloaded / total) * 100), 2)
            job.status = "downloading"
        elif data.get("status") == "finished":
            job.status = "merging"
            job.progress = max(job.progress, 99.0)


def locate_output(job_id: str) -> Optional[Path]:
    matches = sorted(DOWNLOAD_ROOT.glob(f"{job_id}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def release_client(job: DownloadJob) -> None:
    with lock:
        if client_active.get(job.owner) == job.job_id:
            client_active.pop(job.owner, None)


def download_worker(job_id: str) -> None:
    job = jobs[job_id]
    opts = build_format_options(job)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(job.url, download=True)
        final_path = locate_output(job_id)
        if not final_path or not final_path.exists():
            raise RuntimeError("Downloaded file not found")
        with lock:
            job.status = "completed"
            job.progress = 100.0
            job.filepath = final_path
            job.filename = final_path.name
    except Exception as exc:  # noqa: BLE001
        with lock:
            job.status = "error"
            job.error = str(exc)
    finally:
        release_client(job)


async def run_download(job_id: str) -> None:
    await asyncio.to_thread(download_worker, job_id)


async def cleanup_old_files() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        cutoff = datetime.utcnow() - MAX_FILE_AGE
        for path in DOWNLOAD_ROOT.glob("*"):
            try:
                modified = datetime.utcfromtimestamp(path.stat().st_mtime)
            except FileNotFoundError:
                continue
            if modified < cutoff and path.is_file():
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
        with lock:
            stale_jobs = [
                jid
                for jid, job in jobs.items()
                if job.created_at < cutoff and job.status in {"completed", "error"}
            ]
            for jid in stale_jobs:
                jobs.pop(jid, None)


@app.on_event("startup")
async def startup_event() -> None:
    ensure_directories()
    global cleanup_task  # noqa: PLW0603
    cleanup_task = asyncio.create_task(cleanup_old_files())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if cleanup_task:
        cleanup_task.cancel()


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/download")
async def start_download(payload: DownloadPayload, request: Request) -> Dict:
    client_id = get_client_id(request)
    with lock:
        active_job_id = client_active.get(client_id)
        if active_job_id:
            active_job = jobs.get(active_job_id)
            if active_job and active_job.status not in {"completed", "error"}:
                raise HTTPException(status_code=429, detail="Finish the current download first.")
    job_id = uuid4().hex
    job = DownloadJob(job_id=job_id, url=payload.url, quality=payload.quality, owner=client_id)
    with lock:
        jobs[job_id] = job
        client_active[client_id] = job_id
    asyncio.create_task(run_download(job_id))
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def job_status(job_id: str) -> Dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    response = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "filename": job.filename,
    }
    if job.status == "completed":
        response["download_url"] = f"/api/file/{job.job_id}"
    return response


@app.get("/api/file/{job_id}")
async def serve_file(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job or job.status != "completed" or not job.filepath:
        raise HTTPException(status_code=404, detail="File not ready.")
    if not job.filepath.exists():
        raise HTTPException(status_code=410, detail="File expired.")
    media_type = "audio/mpeg" if job.filepath.suffix.lower() == ".mp3" else "video/mp4"
    return FileResponse(
        job.filepath,
        media_type=media_type,
        filename=job.filename or job.filepath.name,
    )
