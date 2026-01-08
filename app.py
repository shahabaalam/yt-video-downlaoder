import os
import shutil
import stat
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional

from flask import (
    Flask,
    after_this_request,
    jsonify,
    request,
    send_file,
)

from downloader import (
    DownloadError,
    available_audio_bitrates,
    available_heights,
    download_playlist,
    download_video,
    is_playlist,
)

app = Flask(__name__, static_folder="static", static_url_path="")

LINK_TTL_SECONDS = 1800
LINK_STORE: Dict[str, Dict[str, Any]] = {}
HISTORY = deque(maxlen=15)

# Use bundled static FFmpeg/FFprobe when present (helpful for hosts like Vercel).
_bin_dir = Path(__file__).parent / "bin"
_ffmpeg = _bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
_ffprobe = _bin_dir / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
def _ensure_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

if _ffmpeg.exists():
    _ensure_executable(_ffmpeg)
    os.environ.setdefault("FFMPEG_BINARY", str(_ffmpeg))
if _ffprobe.exists():
    _ensure_executable(_ffprobe)
    os.environ.setdefault("FFPROBE_BINARY", str(_ffprobe))

def _error_status(exc: Exception) -> int:
    msg = str(exc).lower()
    if any(word in msg for word in ["unavailable", "terminated", "removed", "copyright", "blocked"]):
        return 404
    if any(word in msg for word in ["private", "signin", "age-restricted"]):
        return 403
    return 500


def _cleanup_links() -> None:
    """Remove expired links and their temp directories."""
    now = time.time()
    expired = [token for token, meta in LINK_STORE.items() if now - meta["created_at"] > LINK_TTL_SECONDS]
    for token in expired:
        _delete_link(token)


def _delete_link(token: str) -> None:
    meta = LINK_STORE.pop(token, None)
    if meta:
        shutil.rmtree(meta.get("temp_dir", ""), ignore_errors=True)


def _record_history(
    url: str,
    quality: str,
    filename: str,
    mode: str,
    container: str,
    token: Optional[str] = None,
) -> None:
    HISTORY.appendleft(
        {
            "url": url,
            "quality": quality,
            "container": container,
            "filename": filename,
            "mode": mode,
            "link": f"/api/link/{token}" if token else None,
            "timestamp": int(time.time()),
        }
    )


def _quality_label(container: str, quality: str | int) -> str:
    q_str = str(quality)
    if container in {"mp3", "m4a"}:
        return f"{q_str} kbps" if q_str.isdigit() else q_str
    return f"{q_str}p" if q_str.isdigit() else q_str


@app.route("/")
def index() -> Any:
    return app.send_static_file("index.html")


@app.route("/playlist")
def playlist_page() -> Any:
    return app.send_static_file("playlist.html")


@app.post("/api/formats")
def fetch_formats() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or request.form.get("url")
    if not url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400
    try:
        heights, meta = available_heights(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DownloadError as exc:
        return jsonify({"error": str(exc)}), _error_status(exc)

    if not heights:
        return jsonify({"error": "No video qualities found for this link."}), 404

    return jsonify(
        {
            "qualities": [f"{h}p" for h in heights],
            "containers": ["mp4", "mkv", "m4a"],
            "meta": meta,
        }
    )


@app.post("/api/download")
def handle_download() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or request.form.get("url")
    desired_name = payload.get("filename") or request.form.get("filename") or ""
    container = payload.get("container") or request.form.get("container") or "mp4"
    default_quality = "320" if container in {"m4a", "mp3"} else "1080"
    quality = payload.get("quality") or request.form.get("quality") or default_quality

    if not url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400

    playlist_mode = is_playlist(url)

    try:
        if playlist_mode:
            file_path, temp_dir = download_playlist(
                url, quality=quality, desired_name=desired_name, container=container
            )
        else:
            file_path, temp_dir = download_video(
                url, quality=quality, desired_name=desired_name, container=container
            )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DownloadError as exc:
        return jsonify({"error": str(exc)}), _error_status(exc)

    filename = os.path.basename(file_path)
    quality_label = _quality_label(container, quality)
    mode_label = "playlist" if playlist_mode else "direct"
    _record_history(url, quality_label, filename, mode=mode_label, container=container)

    @after_this_request
    def cleanup(response: Any) -> Any:
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
        return response

    return send_file(file_path, as_attachment=True, download_name=filename)


@app.post("/api/audio-formats")
def fetch_audio_formats() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or request.form.get("url")
    if not url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400
    try:
        bitrates, meta = available_audio_bitrates(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DownloadError as exc:
        return jsonify({"error": str(exc)}), _error_status(exc)

    # Force fixed MP3 options
    fixed_qualities = ["320", "128"]
    return jsonify({"qualities": fixed_qualities, "containers": ["mp3"], "meta": meta})


@app.post("/api/link")
def create_link() -> Any:
    _cleanup_links()
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or request.form.get("url")
    quality = payload.get("quality") or request.form.get("quality") or "1080"
    desired_name = payload.get("filename") or request.form.get("filename") or ""
    container = payload.get("container") or request.form.get("container") or "mp4"

    if not url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400

    try:
        file_path, temp_dir = download_video(url, quality=quality, desired_name=desired_name, container=container)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DownloadError as exc:
        return jsonify({"error": str(exc)}), 500

    token = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    LINK_STORE[token] = {
        "path": file_path,
        "temp_dir": temp_dir,
        "filename": filename,
        "created_at": time.time(),
    }

    quality_label = _quality_label(container, quality)
    _record_history(url, quality_label, filename, mode="link", container=container, token=token)

    return jsonify({"link": f"/api/link/{token}", "filename": filename, "expires_in": LINK_TTL_SECONDS})


@app.get("/api/link/<token>")
def consume_link(token: str) -> Any:
    _cleanup_links()
    meta = LINK_STORE.get(token)
    if not meta:
        return jsonify({"error": "Link not found or expired."}), 404

    file_path = meta["path"]
    filename = meta["filename"]
    temp_dir = meta["temp_dir"]

    @after_this_request
    def cleanup(response: Any) -> Any:
        _delete_link(token)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return response

    return send_file(file_path, as_attachment=True, download_name=filename)


@app.get("/api/history")
def get_history() -> Any:
    _cleanup_links()
    return jsonify({"items": list(HISTORY)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
