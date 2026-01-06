import os
import re
import shutil
import tempfile
from typing import Dict, List, Tuple

import yt_dlp


class DownloadError(Exception):
    """Raised when a download or merge step fails."""


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


def available_heights(url: str) -> List[int]:
    """
    Return sorted unique heights available for the given URL (video formats only).
    """
    _validate_url(url)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(f"Could not fetch formats: {exc}") from exc

    heights = {
        int(fmt["height"])
        for fmt in info.get("formats", [])
        if fmt.get("height") and fmt.get("vcodec") and fmt.get("vcodec") != "none"
    }
    return sorted(heights, reverse=True)


def available_audio_bitrates(url: str) -> List[int]:
    """
    Return sorted unique audio bitrates (abr) available for the given URL.
    """
    _validate_url(url)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(f"Could not fetch audio formats: {exc}") from exc

    bitrates = {
        int(fmt["abr"])
        for fmt in info.get("formats", [])
        if fmt.get("abr") and fmt.get("acodec") and fmt.get("acodec") != "none"
    }
    return sorted(bitrates, reverse=True)


def download_video(
    url: str,
    quality: str | int = "1080",
    desired_name: str = "",
    container: str = "mp4",
) -> Tuple[str, str]:
    """
    Download a YouTube video with selectable quality height and container.
    Returns (final_file_path, temp_dir). Caller is responsible for cleaning up temp_dir.
    """
    _validate_url(url)

    container = container.lower()
    is_audio_only = container == "m4a"

    if container not in {"mp4", "mkv", "m4a"}:
        container = "mp4"

    temp_dir = tempfile.mkdtemp(prefix="yt_dl_")
    fallback_name = "%(title).80s [%(id)s]"
    base_name = _sanitize_filename(desired_name, "video") if desired_name else fallback_name

    if is_audio_only:
        audio_quality = "192"
        match = re.search(r"(\d+)", str(quality))
        if match:
            audio_quality = match.group(1)

        format_selector = "bestaudio[ext=m4a]/bestaudio/best"
        ydl_opts: Dict[str, object] = {
            "format": format_selector,
            "merge_output_format": None,
            "outtmpl": os.path.join(temp_dir, f"{base_name}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": audio_quality}
            ],
        }
    else:
        try:
            height_int = int(str(quality).replace("p", ""))
        except ValueError:
            height_int = 1080

        video_selector = f"bestvideo[height<={height_int}]"
        format_selector = f"{video_selector}+bestaudio/bestvideo+bestaudio/best"
        ydl_opts = {
            "format": format_selector,
            "merge_output_format": container,
            "outtmpl": os.path.join(temp_dir, f"{base_name}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": container},
            ],
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ydl.prepare_filename(info)
    except Exception as exc:  # pragma: no cover - defensive catch for CLI errors
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError(f"Download failed: {exc}") from exc

    final_path = _find_latest_file(temp_dir)
    if not final_path:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError("Merged output not found.")

    if desired_name:
        clean_base = _sanitize_filename(desired_name, "")
        if clean_base:
            ext = os.path.splitext(final_path)[1] or f".{container}"
            custom_path = os.path.join(temp_dir, f"{clean_base}{ext}")
            try:
                os.replace(final_path, custom_path)
                final_path = custom_path
            except OSError:
                pass

    return final_path, temp_dir
