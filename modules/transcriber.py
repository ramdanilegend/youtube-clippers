"""
Module 2: Audio Transcription
Menggunakan faster-whisper untuk transkripsi audio → teks + timestamp.
"""

import os
import json
import subprocess

# Persistent transcript cache — disimpan di video_cache/ agar bisa dipakai lintas session.
# Format: video_cache/{video_id}_transcript.json
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "video_cache")


def _video_id_from_path(video_path: str) -> str:
    """
    Coba ambil video_id dari nama file video.
    Kalau video disimpan sebagai video_cache/{id}.mp4, return id-nya.
    """
    basename = os.path.splitext(os.path.basename(video_path))[0]
    # YouTube video ID: 11 karakter [A-Za-z0-9_-]
    import re
    m = re.fullmatch(r"[A-Za-z0-9_-]{11}", basename)
    return basename if m else ""


def transcribe_video(video_path: str, output_dir: str,
                     model_size: str = "base",
                     language: str = None,
                     device: str = "cpu") -> dict:
    """
    Transkripsi video menjadi teks dengan timestamp per segment.

    Returns:
        dict: {
            "full_text": str,
            "segments": [
                {"start": float, "end": float, "text": str}
            ],
            "language": str
        }
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    # ── Check transcript cache ────────────────────────────────────────────
    video_id = _video_id_from_path(video_path)
    cached_transcript = os.path.join(_CACHE_DIR, f"{video_id}_transcript.json") if video_id else ""

    if video_id and os.path.exists(cached_transcript):
        print(f"[CACHE] Transkripsi sudah ada di cache, skip → {cached_transcript}")
        with open(cached_transcript, encoding="utf-8") as f:
            data = json.load(f)
        # Juga simpan salinan ke output_dir agar pipeline tetap menemukan transcript.json
        out_path = os.path.join(output_dir, "transcript.json")
        if not os.path.exists(out_path):
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        lang = data.get("language", "?")
        nseg = len(data.get("segments", []))
        nword = len(data.get("full_text", "").split())
        print(f"    Bahasa   : {lang}")
        print(f"    Segments : {nseg}")
        print(f"    Total    : {nword} kata")
        return data
    # ─────────────────────────────────────────────────────────────────────

    # Extract audio dari video
    audio_path = os.path.join(output_dir, "audio.wav")
    print("[Transcribe] Extracting audio...")

    extract_cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path
    ]
    subprocess.run(extract_cmd, capture_output=True)

    # Transkripsi dengan faster-whisper
    print(f"[Transcribe] Mentranskripsi dengan model '{model_size}'...")

    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type="int8")
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True
    )

    segments = []
    full_text = ""

    for segment in segments_iter:
        seg_data = {
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": []
        }
        if hasattr(segment, "words") and segment.words:
            for w in segment.words:
                seg_data["words"].append({
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "word": w.word.strip()
                })
        segments.append(seg_data)
        full_text += segment.text + " "

    detected_lang = info.language if info else "unknown"
    print(f"    Bahasa   : {detected_lang}")
    print(f"    Segments : {len(segments)}")
    print(f"    Total    : {len(full_text.split())} kata")

    # Simpan transkripsi
    transcript_path = os.path.join(output_dir, "transcript.json")
    transcript_data = {
        "language": detected_lang,
        "full_text": full_text.strip(),
        "segments": segments
    }

    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    print(f"    Tersimpan: {transcript_path}")

    # ── Simpan ke persistent cache ────────────────────────────────────────
    if video_id and cached_transcript:
        try:
            with open(cached_transcript, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, ensure_ascii=False, indent=2)
            print(f"    [CACHE] Transkripsi disimpan ke cache: {cached_transcript}")
        except Exception:
            pass
    # ─────────────────────────────────────────────────────────────────────

    # Cleanup audio temp
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return transcript_data
