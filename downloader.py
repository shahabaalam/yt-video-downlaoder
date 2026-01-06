import os
import re
import shutil
import tempfile
from typing import Dict, Tuple

import yt_dlp


class DownloadError(Exception):
    """Raised when a download or merge step fails."""


QUALITY_MAP: Dict[str, Dict[str, object]] = {
    "1080p": {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
        "container": "mp4",
        "audio_only": False,
    },
    "720p": {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
        "container": "mp4",
        "audio_only": False,
    },
    "480p": {
        "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
        "container": "mp4",
        "audio_only": False,
    },
    "audio": {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "container": "m4a",
        "audio_only": True,
    },
}


def _validate_url(url: str) -> None:
    if not url or not isinstance(url, str):
        raise ValueError("A URL is required.")
    if not url.startswith(("http://", "https://")):
        raise ValueError("The URL must start with http:// or https://.")

    pattern = r"(youtube\.com|youtu\.be)"
    if re.search(pattern, url, re.IGNORECASE) is None:
        raise ValueError("Only YouTube links are supported in this app.")


def _sanitize_filename(name: str, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9 _()\\-\\.]", "", name).strip()
    return safe or fallback


def _find_latest_file(directory: str) -> str:
    candidates = [
        os.path.join(directory, fname)
        for fname in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, fname))
    ]
    return max(candidates, key=os.path.getmtime) if candidates else ""


def download_video(url: str, quality: str = "1080p", desired_name: str = "") -> Tuple[str, str]:
    """
    Download a YouTube video with selectable quality (1080p/720p/480p/audio).
    Returns (final_file_path, temp_dir). Caller is responsible for cleaning up temp_dir.
    """
    _validate_url(url)

    quality_key = quality if quality in QUALITY_MAP else "1080p"
    opts = QUALITY_MAP[quality_key]
    container = str(opts["container"])
    audio_only = bool(opts["audio_only"])

    temp_dir = tempfile.mkdtemp(prefix="yt_dl_")
    fallback_name = "%(title).80s [%(id)s]"
    base_name = _sanitize_filename(desired_name, "video") if desired_name else fallback_name

    ydl_opts = {
        "format": opts["format"],
        "merge_output_format": None if audio_only else container,
        "outtmpl": os.path.join(temp_dir, f"{base_name}.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "postprocessors": [],
    }

    if audio_only:
        ydl_opts["postprocessors"].append(
            {"key": "FFmpegExtractAudio", "preferredcodec": container, "preferredquality": "192"}
        )
    else:
        ydl_opts["postprocessors"].append({"key": "FFmpegVideoConvertor", "preferedformat": container})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared = ydl.prepare_filename(info)
    except Exception as exc:  # pragma: no cover - defensive catch for CLI errors
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError(f"Download failed: {exc}") from exc

    final_path = _find_latest_file(temp_dir)
    if not final_path:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError("Merged output not found.")

    # Ensure desired custom filename has correct extension (after yt-dlp postprocessing).
    if desired_name:
        clean_base = _sanitize_filename(desired_name, "")
        if clean_base:
            ext = os.path.splitext(final_path)[1] or f".{container}"
            custom_path = os.path.join(temp_dir, f"{clean_base}{ext}")
            try:
                os.replace(final_path, custom_path)
                final_path = custom_path
            except OSError:
                # If rename fails, keep the original.
                pass

    return final_path, temp_dir
