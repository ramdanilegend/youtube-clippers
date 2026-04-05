"""
Module 1: YouTube Video Downloader
Menggunakan yt-dlp untuk download video + metadata + thumbnail.
"""

import os
import json
import re
import subprocess
import sys

# Persistent cache: downloaded videos are stored here by video-ID
# so the same video is never re-downloaded across sessions.
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "video_cache")


def _video_id_from_url(url: str) -> str:
    """Extract YouTube video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


def download_video(url: str, output_dir: str, preferred_quality: str = "720") -> dict:
    """
    Download YouTube video, metadata, dan thumbnail.

    Returns:
        dict: {
            "video_path": str,
            "thumbnail_path": str,
            "title": str,
            "duration": int,
            "channel": str,
            "description": str,
            "url": str
        }
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    # ── Check video cache ─────────────────────────────────────────────────
    video_id = _video_id_from_url(url)
    cached_video  = os.path.join(_CACHE_DIR, f"{video_id}.mp4")   if video_id else ""
    cached_meta   = os.path.join(_CACHE_DIR, f"{video_id}.json")  if video_id else ""

    if video_id and os.path.exists(cached_video) and os.path.exists(cached_meta):
        print(f"[CACHE] Video sudah ada di cache, skip download → {cached_video}")
        with open(cached_meta, encoding="utf-8") as f:
            cached = json.load(f)
        # Copy/symlink thumbnail into session dir
        title       = cached["title"]
        thumb_dst   = os.path.join(output_dir, f"{title}_thumb.jpg")
        if cached.get("thumbnail_path") and os.path.exists(cached["thumbnail_path"]):
            import shutil as _sh
            _sh.copy2(cached["thumbnail_path"], thumb_dst)
        cached["video_path"]     = cached_video
        cached["thumbnail_path"] = thumb_dst if os.path.exists(thumb_dst) else cached.get("thumbnail_path", "")
        print(f"    Judul   : {cached['title']}")
        print(f"    Channel : {cached['channel']}")
        dur = cached.get("duration", 0)
        print(f"    Durasi  : {dur // 60}m {dur % 60}s")
        return cached
    # ─────────────────────────────────────────────────────────────────────

    # Step 1: Ambil metadata dulu
    print("[1/3] Mengambil metadata video...")
    meta_cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-download",
        "--no-check-certificates",
        url
    ]

    result = subprocess.run(meta_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Gagal mengambil metadata: {result.stderr}")

    metadata = json.loads(result.stdout)
    title = sanitize_filename(metadata.get("title", "video"))
    duration = metadata.get("duration", 0)
    channel = metadata.get("channel", "Unknown")
    description = metadata.get("description", "")

    print(f"    Judul   : {title}")
    print(f"    Channel : {channel}")
    print(f"    Durasi  : {duration // 60}m {duration % 60}s")

    # Step 2: Download thumbnail
    print("[2/3] Mendownload thumbnail...")
    thumbnail_path = os.path.join(output_dir, f"{title}_thumb.jpg")
    thumb_cmd = [
        sys.executable, "-m", "yt_dlp",
        "--write-thumbnail",
        "--skip-download",
        "--convert-thumbnails", "jpg",
        "-o", os.path.join(output_dir, f"{title}_thumb"),
        "--no-playlist",
        "--no-check-certificates",
        url
    ]
    subprocess.run(thumb_cmd, capture_output=True, text=True)

    # Cari thumbnail file (bisa .jpg atau .webp)
    if not os.path.exists(thumbnail_path):
        for f in os.listdir(output_dir):
            if "thumb" in f.lower() and f.endswith((".jpg", ".jpeg", ".png", ".webp")):
                thumbnail_path = os.path.join(output_dir, f)
                break

    if os.path.exists(thumbnail_path):
        print(f"    Thumbnail: {thumbnail_path}")
    else:
        print("    [WARNING] Thumbnail tidak ditemukan, akan pakai frame pertama")
        thumbnail_path = ""

    # Step 3: Download video (save directly to cache if we have a video_id)
    print("[3/3] Mendownload video...")
    if video_id:
        video_path = cached_video          # save into cache folder
    else:
        video_path = os.path.join(output_dir, f"{title}.mp4")

    download_cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", f"bestvideo[height<={preferred_quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={preferred_quality}][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", video_path,
        "--no-playlist",
        "--no-overwrites",
        "--no-check-certificates",
        url
    ]

    result = subprocess.run(download_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Gagal download video: {result.stderr}")

    # Cari file yang di-download (yt-dlp kadang tambah suffix)
    if not os.path.exists(video_path):
        for f in os.listdir(os.path.dirname(video_path) or output_dir):
            if f.endswith(".mp4"):
                video_path = os.path.join(os.path.dirname(video_path) or output_dir, f)
                break

    # Kalau thumbnail gagal, extract frame pertama dari video
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        thumbnail_path = os.path.join(output_dir, f"{title}_thumb.jpg")
        extract_cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vframes", "1", "-q:v", "2",
            thumbnail_path
        ]
        subprocess.run(extract_cmd, capture_output=True)

    print(f"    Tersimpan: {video_path}")

    result_meta = {
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "title": title,
        "duration": duration,
        "channel": channel,
        "description": description[:500],
        "url": url
    }

    # ── Save to cache for future runs ─────────────────────────────────────
    if video_id and os.path.exists(video_path):
        try:
            with open(cached_meta, "w", encoding="utf-8") as f:
                json.dump(result_meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    # ─────────────────────────────────────────────────────────────────────

    return result_meta


def download_multiple(urls: list, output_base_dir: str,
                      preferred_quality: str = "720") -> list:
    """
    Download multiple YouTube videos.

    Returns:
        list[dict]: List of video metadata dicts
    """
    all_meta = []
    for i, url in enumerate(urls, 1):
        print(f"\n--- Video {i}/{len(urls)} ---")
        download_dir = os.path.join(output_base_dir, f"source_{i:02d}")
        try:
            meta = download_video(url, download_dir, preferred_quality)
            meta["source_index"] = i
            all_meta.append(meta)
        except Exception as e:
            print(f"    [ERROR] Gagal download video {i}: {e}")
    return all_meta


def sanitize_filename(name: str) -> str:
    """Bersihkan nama file dari karakter ilegal."""
    illegal = '<>:"/\\|?*'
    for char in illegal:
        name = name.replace(char, "")
    return name[:100].strip()
