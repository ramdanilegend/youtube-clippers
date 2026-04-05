# 🎬 YouTube Auto Clipper v2

Pipeline otomatis untuk membuat short-form clips dari video YouTube — lengkap dengan subtitle burned-in, TTS voiceover, intro/outro, dan branding.

## ✨ Fitur

- **Download otomatis** dari YouTube dengan cache persistent (skip re-download)
- **Transkripsi** menggunakan Whisper (word-level timestamps, cache persistent)
- **AI Analisis** momen terbaik via Claude atau GPT-4o
- **Subtitle burned-in** — bold white text, black outline, keyword highlight kuning
- **TTS Voiceover** intro & outro via Edge-TTS (bahasa Indonesia/Inggris)
- **Format vertikal** (9:16 YouTube Shorts) atau horizontal (16:9)
- **Multi-video** — gabungkan momen terbaik dari beberapa video sekaligus

## 🚀 Cara Pakai

### Install

```bash
# Clone / download project
cd youtube-clipper

# Setup otomatis (buat venv + install dependencies)
bash setup.sh        # macOS / Linux
setup.bat            # Windows

# Salin config dan isi API key
cp config.example.py config.py
# Edit config.py → isi OPENAI_API_KEY atau ANTHROPIC_API_KEY
```

### Jalankan

```bash
# Satu video
python clipper.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Multi video (cari momen terbaik dari semua video)
python clipper.py "https://youtu.be/ID1" "https://youtu.be/ID2"

# Dengan context/arahan khusus
python clipper.py "https://youtu.be/ID" --context "fokus tips bisnis dan insight mengejutkan"
```

Output tersimpan di `output/session_YYYYMMDD_HHMMSS/`.

## 🛠️ Konfigurasi

Edit `config.py` (salin dari `config.example.py`):

| Setting | Default | Keterangan |
|---|---|---|
| `LLM_PROVIDER` | `"openai"` | `"openai"` atau `"anthropic"` |
| `LLM_MODEL` | `"gpt-4o-mini"` | Model LLM untuk analisis |
| `WHISPER_MODEL` | `"base"` | `tiny` (cepat) → `large-v3` (akurat) |
| `CLIP_FORMAT` | `"vertical"` | `"vertical"` (Shorts 9:16) / `"horizontal"` (16:9) |
| `MAX_CLIPS` | `10` | Jumlah clip yang dibuat |
| `CLIP_MIN_DURATION` | `30` | Minimum durasi clip (detik) |
| `CLIP_MAX_DURATION` | `90` | Maksimum durasi clip (detik) |
| `TTS_VOICE` | `id-ID-ArdiNeural` | Voice TTS ([daftar lengkap](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)) |

## 📁 Struktur Project

```
youtube-clipper/
├── clipper.py              # Entry point utama
├── config.py               # API keys & settings (tidak di-commit)
├── config.example.py       # Template config
├── requirements.txt
├── setup.sh / setup.bat
├── modules/
│   ├── downloader.py       # Download YouTube + cache
│   ├── transcriber.py      # Whisper transcription + cache
│   ├── analyzer.py         # AI analisis momen terbaik
│   ├── tts_engine.py       # TTS voiceover (Edge-TTS)
│   └── video_editor.py     # FFmpeg: cut, crop, subtitle, merge
├── video_cache/            # Cache video & transcript (tidak di-commit)
└── output/                 # Hasil clip (tidak di-commit)
```

## ⚡ Cache System

- **Video cache**: `video_cache/{video_id}.mp4` — video tidak perlu di-download ulang
- **Transcript cache**: `video_cache/{video_id}_transcript.json` — transkripsi tidak perlu diulang

Kedua cache persistent lintas session. Hapus file cache kalau ingin force re-download/re-transcribe.

## 📦 Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — download YouTube
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — transkripsi audio
- [edge-tts](https://github.com/rany2/edge-tts) — Text-to-Speech
- [Pillow](https://python-pillow.org/) — render subtitle PNG
- [FFmpeg](https://ffmpeg.org/) — video processing (harus terinstall di sistem)
- OpenAI / Anthropic SDK — AI analisis

## ⚠️ Requirements

- Python 3.10+
- FFmpeg terinstall (`brew install ffmpeg` di macOS)
- API key OpenAI atau Anthropic (beli credit terpisah dari subscription)
