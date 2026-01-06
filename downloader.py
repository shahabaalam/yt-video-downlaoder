import os
import re
import shutil
import tempfile
from typing import Tuple

import yt_dlp


class DownloadError(Exception):
    """Raised when a download or merge step fails."""


def _validate_url(url: str) -> None:
    if not url or not isinstance(url, str):
        raise ValueError("A URL is required.")
    if not url.startswith(("http://", "https://")):
        raise ValueError("The URL must start with http:// or https://.")

    # Basic YouTube host check; still let yt-dlp handle the heavy lifting.
    pattern = r"(youtube\.com|youtu\.be)"
    if re.search(pattern, url, re.IGNORECASE) is None:
        raise ValueError("Only YouTube links are supported in this app.")


def _merged_output_path(prepared_filename: str) -> str:
    stem, _ = os.path.splitext(prepared_filename)
    return f"{stem}.mp4"


def download_video(url: str) -> Tuple[str, str]:
    """
    Download a YouTube video at up to 1080p with audio merged.

    Returns (final_file_path, temp_dir). Caller is responsible for cleaning up
    temp_dir when finished sending the file.
    """
    _validate_url(url)

    temp_dir = tempfile.mkdtemp(prefix="yt_dl_")
    format_selector = (
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=1080]+bestaudio/best"
    )

    ydl_opts = {
        "format": format_selector,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(temp_dir, "%(title).80s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared = ydl.prepare_filename(info)
    except Exception as exc:  # pragma: no cover - defensive catch for CLI errors
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError(f"Download failed: {exc}") from exc

    final_path = _merged_output_path(prepared)
    if not os.path.exists(final_path):
        # yt-dlp sometimes preserves the container extension; fall back to whatever exists.
        candidates = [
            os.path.join(temp_dir, fname)
            for fname in os.listdir(temp_dir)
            if os.path.isfile(os.path.join(temp_dir, fname))
        ]
        if candidates:
            final_path = max(candidates, key=os.path.getmtime)

    if not os.path.exists(final_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError("Merged output not found.")

    return final_path, temp_dir
