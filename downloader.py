import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Tuple, cast

import yt_dlp

class DownloadError(Exception):
    """Raised when a download or merge step fails."""


COOKIES_ENV = (os.environ.get("YTDLP_COOKIES") or os.environ.get("YOUTUBE_COOKIES") or "").strip()
COOKIES_FILE = ""
if COOKIES_ENV:
    if os.path.isfile(COOKIES_ENV):
        COOKIES_FILE = COOKIES_ENV
    else:
        try:
            # If env contains raw cookie text, persist it to a temp file for yt-dlp
            tmp = tempfile.NamedTemporaryFile(delete=False, prefix="yt_cookies_", suffix=".txt")
            tmp.write(COOKIES_ENV.encode("utf-8"))
            tmp.close()
            COOKIES_FILE = tmp.name
        except Exception:
            COOKIES_FILE = ""


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

def is_playlist(url: str) -> bool:
    """
    Return True if the URL points to a playlist (based on yt-dlp metadata).
    """
    _validate_url(url)
    try:
        # Fix: Cast to 'Any' to completely bypass the strict TypedDict check
        with yt_dlp.YoutubeDL(
            cast(Any, {
                "quiet": True,
                "skip_download": True,
                "extract_flat": True,
                "noplaylist": False,
            })
        ) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return False

    return bool(info and (info.get("_type") == "playlist" or info.get("entries")))


def available_heights(url: str) -> Tuple[List[int], Dict[str, str]]:
    """
    Return (heights, meta) where heights are sorted unique video heights and meta has title/thumbnail.
    """
    _validate_url(url)
    try:
        # Pass dict directly to avoid TypedDict mismatch
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "cookiefile": COOKIES_FILE or None}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return [], {"title": "", "thumbnail": ""}
    except Exception as exc:
        raise DownloadError(f"Could not fetch formats: {exc}") from exc

    heights = {
        int(fmt["height"])
        for fmt in (info.get("formats") or [])
        if fmt.get("height") and fmt.get("vcodec") and fmt.get("vcodec") != "none"
    }
    meta = {
        "title": info.get("title") or "",
        "thumbnail": info.get("thumbnail") or "",
    }
    if not meta["thumbnail"]:
        thumbs = info.get("thumbnails") or []
        if thumbs:
            meta["thumbnail"] = thumbs[-1].get("url") or ""

    return sorted(heights, reverse=True), meta


def available_audio_bitrates(url: str) -> Tuple[List[int], Dict[str, str]]:
    """
    Return (bitrates, meta) where bitrates is sorted unique audio abr values
    and meta includes title + thumbnail for UI previews.
    """
    _validate_url(url)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "cookiefile": COOKIES_FILE or None}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return [], {"title": "", "thumbnail": ""}
    except Exception as exc:
        raise DownloadError(f"Could not fetch audio formats: {exc}") from exc

    bitrates = {
        int(fmt["abr"])
        for fmt in (info.get("formats") or [])
        if fmt.get("abr") and fmt.get("acodec") and fmt.get("acodec") != "none"
    }
    
    meta = {
        "title": info.get("title") or "",
        "thumbnail": info.get("thumbnail") or "",
    }
    
    # Fallback to the last thumbnail in the list if the main one is missing
    if not meta["thumbnail"]:
        thumbs = info.get("thumbnails") or []
        if thumbs:
            meta["thumbnail"] = thumbs[-1].get("url") or ""

    return sorted(bitrates, reverse=True), meta


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
    is_audio_only = container in {"m4a", "mp3"}

    if container not in {"mp4", "mkv", "m4a", "mp3"}:
        container = "mp4"

    temp_dir = tempfile.mkdtemp(prefix="yt_dl_")
    fallback_name = "%(title).80s [%(id)s]"
    base_name = _sanitize_filename(desired_name, "video") if desired_name else fallback_name

    try:
        if is_audio_only:
            quality_str = str(quality).lower()
            match = re.search(r"(\d+)", quality_str)
            best_audio_requested = quality_str in {"best", "max", "highest"} or not match

            # Define postprocessors as a generic List[Dict]
            postprocessors: List[Dict[str, Any]] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3" if container == "mp3" else "m4a",
                }
            ]

            if best_audio_requested:
                format_selector = "bestaudio/best"
            else:
                max_abr = match.group(1) if match else "320"
                format_selector = (
                    f"bestaudio[abr<={max_abr}][ext=m4a]/"
                    f"bestaudio[abr<={max_abr}]/"
                    "bestaudio/best"
                )
                postprocessors[0]["preferredquality"] = max_abr

            with yt_dlp.YoutubeDL({
                "format": format_selector,
                "outtmpl": os.path.join(temp_dir, f"{base_name}.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                # Fix: Cast the list to Any to satisfy the strict Type Checker
                "postprocessors": cast(List[Any], postprocessors),
                "cookiefile": COOKIES_FILE or None,
            }) as ydl:
                info = ydl.extract_info(url, download=True)
        else:
            try:
                height_int = int(str(quality).replace("p", ""))
            except ValueError:
                height_int = 1080

            video_selector = f"bestvideo[height<={height_int}]"
            format_selector = f"{video_selector}+bestaudio/bestvideo+bestaudio/best"

            with yt_dlp.YoutubeDL({
                "format": format_selector,
                "merge_output_format": container,
                "outtmpl": os.path.join(temp_dir, f"{base_name}.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegVideoConvertor",
                    # yt-dlp expects the misspelled 'preferedformat'
                    "preferedformat": container,
                }],
                "cookiefile": COOKIES_FILE or None,
            }) as ydl:
                info = ydl.extract_info(url, download=True)

    except Exception as exc:
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


def download_playlist(
    url: str,
    quality: str | int = "1080",
    desired_name: str = "",
    container: str = "mp4",
) -> Tuple[str, str]:
    """
    Download an entire playlist as a ZIP of individual files.
    Returns (zip_path, temp_dir). Caller cleans up temp_dir.
    """
    _validate_url(url)

    container = container.lower()
    is_audio_only = container in {"m4a", "mp3"}
    if container not in {"mp4", "mkv", "m4a", "mp3"}:
        container = "mp4"

    temp_dir = tempfile.mkdtemp(prefix="yt_pl_")
    files_dir = os.path.join(temp_dir, "files")
    os.makedirs(files_dir, exist_ok=True)

    fallback_name = "%(playlist_title).80s"
    base_name = _sanitize_filename(desired_name, "") if desired_name else ""
    playlist_label = base_name or fallback_name
    file_pattern = os.path.join(files_dir, f"%(playlist_index)03d - %(title).80s.%(ext)s")

    try:
        if is_audio_only:
            quality_str = str(quality).lower()
            match = re.search(r"(\d+)", quality_str)
            best_audio_requested = quality_str in {"best", "max", "highest"} or not match

            postprocessors: List[Dict[str, Any]] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3" if container == "mp3" else "m4a",
                }
            ]

            if best_audio_requested:
                format_selector = "bestaudio/best"
            else:
                max_abr = match.group(1) if match else "320"
                format_selector = (
                    f"bestaudio[abr<={max_abr}][ext=m4a]/"
                    f"bestaudio[abr<={max_abr}]/"
                    "bestaudio/best"
                )
                postprocessors[0]["preferredquality"] = max_abr

            with yt_dlp.YoutubeDL({
                "format": format_selector,
                "outtmpl": file_pattern,
                "noplaylist": False,
                "quiet": True,
                "ignoreerrors": True,
                "postprocessors": cast(List[Any], postprocessors),
                "cookiefile": COOKIES_FILE or None,
            }) as ydl:
                ydl.extract_info(url, download=True)
        else:
            try:
                height_int = int(str(quality).replace("p", ""))
            except ValueError:
                height_int = 1080

            video_selector = f"bestvideo[height<={height_int}]"
            format_selector = f"{video_selector}+bestaudio/bestvideo+bestaudio/best"

            with yt_dlp.YoutubeDL({
                "format": format_selector,
                "merge_output_format": container,
                "outtmpl": file_pattern,
                "noplaylist": False,
                "quiet": True,
                "ignoreerrors": True,
                "postprocessors": [{
                    "key": "FFmpegVideoConvertor",
                    # yt-dlp expects the misspelled 'preferedformat'
                    "preferedformat": container,
                }],
                "cookiefile": COOKIES_FILE or None,
            }) as ydl:
                ydl.extract_info(url, download=True)

    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError(f"Playlist download failed: {exc}") from exc

    # Zip the downloaded files
    zip_base = os.path.join(temp_dir, _sanitize_filename(playlist_label, "playlist"))
    zip_path = shutil.make_archive(zip_base, "zip", files_dir)
    if not os.path.isfile(zip_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError("Playlist archive not created.")

    return zip_path, temp_dir
