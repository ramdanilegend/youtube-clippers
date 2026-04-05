"""
=============================================================
  KONFIGURASI YOUTUBE AUTO CLIPPER
=============================================================
  Salin file ini menjadi config.py, lalu isi API key kamu.
  JANGAN commit config.py ke Git (sudah ada di .gitignore).
"""

# ─── API Keys ──────────────────────────────────────────────
OPENAI_API_KEY = ""          # sk-...   (untuk GPT-4o / GPT-4o-mini)
ANTHROPIC_API_KEY = ""       # sk-ant-... (untuk Claude)

# Provider yang dipakai: "openai" atau "anthropic"
LLM_PROVIDER = "openai"

# Model yang dipakai
LLM_MODEL = "gpt-4o-mini"   # Alternatif: "claude-3-5-haiku-20241022", "gpt-4o"

# ─── Video Download ────────────────────────────────────────
MAX_VIDEO_DURATION = 7200    # Maks durasi video (detik). Default 2 jam.
DOWNLOAD_FORMAT = "mp4"
PREFERRED_QUALITY = "720"    # 360, 480, 720, 1080

# ─── Whisper Transcription ─────────────────────────────────
WHISPER_MODEL = "base"       # tiny, base, small, medium, large-v3
WHISPER_LANGUAGE = None      # None = auto-detect. Atau: "id", "en", "ja", dll
WHISPER_DEVICE = "cpu"       # "cpu" atau "cuda" (kalau punya GPU NVIDIA)

# ─── Clip Settings ─────────────────────────────────────────
MAX_CLIPS = 10               # Maks jumlah clip per video
CLIP_MIN_DURATION = 30       # Minimum durasi clip (detik)
CLIP_MAX_DURATION = 90       # Maksimum durasi clip (detik)
CLIP_FORMAT = "vertical"     # "vertical" (9:16 Shorts) atau "horizontal" (16:9)

# ─── TTS Voice ─────────────────────────────────────────────
TTS_VOICE = "id-ID-ArdiNeural"       # Suara bahasa Indonesia (pria)
# TTS_VOICE = "id-ID-GadisNeural"    # Suara bahasa Indonesia (wanita)
# TTS_VOICE = "en-US-GuyNeural"      # Suara bahasa Inggris (pria)
TTS_RATE = "+0%"                     # Kecepatan bicara: "-10%", "+0%", "+20%"

# ─── Intro / Outro ────────────────────────────────────────
OUTRO_CTA_TEXT = "Subscribe & Like untuk konten menarik lainnya!"
OUTRO_DURATION = 4.0

# ─── Logo ──────────────────────────────────────────────────
LOGO_PATH = ""               # Contoh: "./assets/logo.png"
LOGO_SIZE = 120
LOGO_POSITION = "top-left"
LOGO_OPACITY = 0.8

# ─── Visual Style ──────────────────────────────────────────
SUBTITLE_FONT_SIZE = 42
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = "black@0.6"
BRAND_TEXT = ""
BRAND_POSITION = "top-right"

# ─── Output ────────────────────────────────────────────────
OUTPUT_DIR = "./output"
