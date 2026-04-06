#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════╗
║            YOUTUBE AUTO CLIPPER PIPELINE  v2                  ║
║                                                               ║
║  Usage (single video):                                        ║
║    python clipper.py <url>                                    ║
║                                                               ║
║  Usage (multi video - digabung):                              ║
║    python clipper.py <url1> <url2> <url3>                     ║
║                                                               ║
║  Usage (dengan context/arahan):                               ║
║    python clipper.py <url> --context "fokus tips investasi"   ║
║    python clipper.py <url1> <url2> --context "cari momen lucu"║
║                                                               ║
║  Output per session:                                          ║
║    clips/        → video clips final siap review              ║
║    REVIEW_CHECKLIST.md → checklist + draft judul/deskripsi    ║
║    transcript.json / analysis.json → data lengkap             ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import sys

# ── Auto-relaunch with venv Python if running under system Python ──────────
_VENV_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "venv", "bin", "python3")
if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable) != os.path.abspath(_VENV_PY):
    os.execv(_VENV_PY, [_VENV_PY] + sys.argv)
# ───────────────────────────────────────────────────────────────────────────
import json
import argparse
from datetime import datetime

from modules.downloader import download_video, download_multiple
from modules.transcriber import transcribe_video
from modules.analyzer import analyze_transcript, analyze_multi_transcripts
from modules.tts_engine import generate_clip_voiceovers
from modules.video_editor import create_clip, create_compilation, create_intro_video
from modules.tts_engine import generate_voiceover, get_audio_duration

import config


def parse_args():
    parser = argparse.ArgumentParser(
        description="YouTube Auto Clipper",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="YouTube URL(s). Satu atau lebih, pisahkan dengan spasi."
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        default="",
        help=(
            "Konteks/arahan untuk AI. Contoh:\n"
            '  --context "fokus tips investasi"\n'
            '  --context "cari momen lucu dan mengejutkan"\n'
            '  --context "highlight insight tentang startup"'
        )
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        default=False,
        help=(
            "Gabungkan potongan terbaik dari SEMUA video sumber menjadi\n"
            "SATU video compilation. Cocok untuk momen lucu/highlight\n"
            "dari beberapa video yang dikombinasikan.\n"
            "Contoh: python clipper.py <url1> <url2> --combine --context \"momen lucu\""
        )
    )
    return parser.parse_args()


def main():
    print_banner()
    args = parse_args()

    # ─── Kumpulkan URL ────────────────────────────────────
    urls    = args.urls
    context = args.context.strip()
    combine = args.combine

    # Default context jika tidak diisi
    if not context:
        context = (
            "Cari momen paling menarik dan berpotensi viral: "
            "insight mengejutkan, pernyataan kontroversial, momen lucu, "
            "cerita emosional, tips praktis, atau fakta menarik yang bikin penonton penasaran. "
            "Pilih yang paling engaging dan bisa berdiri sendiri sebagai konten pendek."
        )
        print(f"\n💡 Menggunakan default context (cari momen viral terbaik)")

    if not urls:
        raw = input("\n🔗 Paste YouTube URL (bisa lebih dari satu, pisahkan spasi):\n> ").strip()
        urls = [u.strip() for u in raw.split() if u.strip()]

    # Validasi
    valid_urls = []
    for u in urls:
        if "youtube.com" in u or "youtu.be" in u:
            valid_urls.append(u)
        else:
            print(f"⚠️  Bukan URL YouTube, dilewati: {u}")

    if not valid_urls:
        print("❌ Tidak ada URL YouTube yang valid.")
        sys.exit(1)

    is_multi = len(valid_urls) > 1

    if context:
        print(f"\n🎯 Context: {context}")
    if is_multi:
        print(f"🔗 Multi-video mode: {len(valid_urls)} video akan digabung")
    if combine:
        print(f"🎞️  Combine mode: momen terbaik dari semua video → 1 video compilation")

    # ─── Validate API key ─────────────────────────────────
    api_key = get_api_key()
    if not api_key:
        print("❌ API key belum diisi! Edit config.py dan isi OPENAI_API_KEY atau ANTHROPIC_API_KEY")
        sys.exit(1)

    # ─── Setup session dir ────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(config.OUTPUT_DIR, f"session_{timestamp}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"\n📁 Output: {os.path.abspath(session_dir)}")

    # ═════════════════════════════════════════════════════
    # STEP 1: Download Video(s)
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"📥 STEP 1: Download {'Videos' if is_multi else 'Video'}")
    print("=" * 60)

    download_base = os.path.join(session_dir, "source")

    if is_multi:
        videos_meta = download_multiple(
            urls=valid_urls,
            output_base_dir=download_base,
            preferred_quality=config.PREFERRED_QUALITY
        )
        if not videos_meta:
            print("❌ Semua video gagal di-download.")
            sys.exit(1)
        # Gunakan video pertama sebagai primary untuk thumbnail
        primary_meta = videos_meta[0]
    else:
        primary_meta = download_video(
            url=valid_urls[0],
            output_dir=download_base,
            preferred_quality=config.PREFERRED_QUALITY
        )
        primary_meta["source_index"] = 1
        videos_meta = [primary_meta]

    # Cek durasi
    for vm in videos_meta:
        if vm["duration"] > config.MAX_VIDEO_DURATION:
            print(f"⚠️  Video '{vm['title']}' terlalu panjang, dilewati.")
            videos_meta = [v for v in videos_meta if v != vm]

    if not videos_meta:
        print("❌ Tidak ada video yang valid.")
        sys.exit(1)

    # ═════════════════════════════════════════════════════
    # STEP 2: Transcribe All Videos
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("🎙️  STEP 2: Transkripsi Audio")
    print("=" * 60)

    transcripts = []
    for vm in videos_meta:
        print(f"\n  Transkripsi: {vm['title']}")
        transcript_dir = os.path.join(session_dir, f"transcript_{vm['source_index']:02d}")
        t = transcribe_video(
            video_path=vm["video_path"],
            output_dir=transcript_dir,
            model_size=config.WHISPER_MODEL,
            language=config.WHISPER_LANGUAGE,
            device=config.WHISPER_DEVICE
        )
        transcripts.append(t)

    # ═════════════════════════════════════════════════════
    # STEP 3: AI Analysis
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("🧠 STEP 3: AI Analisis - Cari Momen Penting")
    print("=" * 60)

    # Combine mode: request shorter segments, more of them, from multiple sources
    clip_min = 15 if combine else config.CLIP_MIN_DURATION
    clip_max = 35 if combine else config.CLIP_MAX_DURATION
    max_clips = config.MAX_CLIPS   # sama untuk semua mode; combine cukup pakai durasi lebih pendek
    combine_hint = (
        " PENTING: pilih momen dari BERBAGAI video sumber yang berbeda "
        "(bukan dari satu video saja). Variasikan sumber video."
    ) if combine and is_multi else ""

    if is_multi:
        clips_data = analyze_multi_transcripts(
            transcripts=transcripts,
            videos_meta=videos_meta,
            max_clips=max_clips,
            clip_min_duration=clip_min,
            clip_max_duration=clip_max,
            provider=config.LLM_PROVIDER,
            api_key=api_key,
            model=config.LLM_MODEL,
            context=context + combine_hint
        )
    else:
        clips_data = analyze_transcript(
            transcript=transcripts[0],
            video_meta=videos_meta[0],
            max_clips=max_clips,
            clip_min_duration=clip_min,
            clip_max_duration=clip_max,
            provider=config.LLM_PROVIDER,
            api_key=api_key,
            model=config.LLM_MODEL,
            context=context
        )

    if not clips_data:
        print("❌ Tidak ditemukan momen penting. Coba URL atau context lain.")
        sys.exit(1)

    # Simpan analysis
    with open(os.path.join(session_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(clips_data, f, ensure_ascii=False, indent=2)

    # ═════════════════════════════════════════════════════
    # STEP 4: Generate Voiceovers
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("🔊 STEP 4: Generate Voiceover (Intro & Outro)")
    print("=" * 60)

    voiceover_dir = os.path.join(session_dir, "voiceovers")
    voiceovers = {}
    for clip in clips_data:
        vo = generate_clip_voiceovers(
            clip_data=clip,
            output_dir=voiceover_dir,
            voice=config.TTS_VOICE,
            rate=config.TTS_RATE,
            outro_cta_text=config.OUTRO_CTA_TEXT
        )
        voiceovers[clip["clip_number"]] = vo

    # ═════════════════════════════════════════════════════
    # STEP 5: Create Video Clips
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("🎬 STEP 5: Membuat Video Clips")
    print("=" * 60)

    clips_dir = os.path.join(session_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    final_clips = []

    for clip in clips_data:
        clip_num = clip["clip_number"]
        vo_data  = voiceovers.get(clip_num, {})

        # Tentukan video sumber
        src_video_idx = clip.get("source_video", 1)
        src_meta = next(
            (v for v in videos_meta if v.get("source_index") == src_video_idx),
            videos_meta[0]
        )
        src_transcript = (transcripts[videos_meta.index(src_meta)]
                          if src_meta in videos_meta else transcripts[0])

        clip_path = create_clip(
            video_path=src_meta["video_path"],
            clip_data=clip,
            voiceover_data=vo_data,
            transcript_segments=src_transcript["segments"],
            output_dir=clips_dir,
            thumbnail_path=src_meta.get("thumbnail_path", ""),
            clip_format=config.CLIP_FORMAT,
            subtitle_font_size=config.SUBTITLE_FONT_SIZE,
            subtitle_color=config.SUBTITLE_FONT_COLOR,
            subtitle_bg=config.SUBTITLE_BG_COLOR,
            brand_text=config.BRAND_TEXT,
            brand_position=config.BRAND_POSITION,
            logo_path=config.LOGO_PATH,
            logo_size=config.LOGO_SIZE,
            logo_position=config.LOGO_POSITION,
            logo_opacity=config.LOGO_OPACITY,
            outro_cta_text=config.OUTRO_CTA_TEXT,
            outro_duration=config.OUTRO_DURATION,
            compile_mode=combine,   # skip per-clip intro/merge when combining
        )

        final_clips.append({
            "clip_number": clip_num,
            "path": clip_path,
            "source_video": src_video_idx,
            "source_channel": src_meta.get("channel", ""),
            "data": clip
        })

    # ═════════════════════════════════════════════════════
    # STEP 5.5 (combine mode): build compilation videos
    # ═════════════════════════════════════════════════════
    if combine:
        print("\n" + "=" * 60)
        print("🎞️  STEP 5.5: Membuat Compilation Videos")
        print("=" * 60)

        res_w = 1080 if config.CLIP_FORMAT == "vertical" else 1920
        res_h = 1920 if config.CLIP_FORMAT == "vertical" else 1080

        # Collect valid segments (include clip metadata for per-compilation intro)
        segments = []
        for fc in final_clips:
            if fc["path"] and os.path.exists(fc["path"]):
                segments.append({
                    "path":              fc["path"],
                    "title":             fc["data"].get("title", ""),
                    "source":            fc["source_channel"],
                    "clip_number":       fc["clip_number"],
                    "viral_score":       fc["data"].get("viral_score", 5),
                    "hook":              fc["data"].get("hook", ""),
                    "commentary_intro":  fc["data"].get("commentary_intro", ""),
                })

        if not segments:
            print("    [WARNING] Tidak ada segment untuk digabung")
        else:
            # Split segments into groups of SEGMENTS_PER_COMPILATION
            SEGMENTS_PER_COMP = 3
            groups = [segments[i:i + SEGMENTS_PER_COMP]
                      for i in range(0, len(segments), SEGMENTS_PER_COMP)]

            print(f"    {len(segments)} segment → {len(groups)} compilation "
                  f"(@{SEGMENTS_PER_COMP} segment per file)")

            comp_dir = os.path.join(session_dir, "compilations")
            os.makedirs(comp_dir, exist_ok=True)

            for gi, group in enumerate(groups, start=1):
                seg_labels = ", ".join(f"#{s['clip_number']}" for s in group)
                print(f"\n    [Compilation {gi}/{len(groups)}] "
                      f"{len(group)} segment: {seg_labels}")

                intro_dir = os.path.join(comp_dir, f"comp_{gi:02d}_tmp")
                os.makedirs(intro_dir, exist_ok=True)

                # ── Build group-specific intro context ──────────────
                # Hook: ambil dari clip dengan viral_score tertinggi di group
                best = max(group, key=lambda s: s.get("viral_score", 0))
                hook_text = best.get("hook", "") or context[:80] or "Momen Terbaik"

                # Narasi: rangkum judul semua clip di group ini
                titles = [s["title"] for s in group]
                if len(titles) == 1:
                    narration = f"Momen lucu yang bikin ngakak! {titles[0]}!"
                elif len(titles) == 2:
                    narration = (f"Dua momen paling lucu hari ini: "
                                 f"{titles[0]}, dan {titles[1]}!")
                else:
                    narration = (f"Kumpulan momen lucu yang bikin ngakak! "
                                 f"{titles[0]}, {titles[1]}, "
                                 f"dan {titles[2]}!")

                # Generate TTS khusus untuk compilation ini
                print(f"      Hook     : {hook_text[:60]}")
                print(f"      Narasi   : {narration[:60]}")
                vo_audio = os.path.join(intro_dir, "comp_intro_vo.mp3")
                try:
                    generate_voiceover(narration, vo_audio,
                                       config.TTS_VOICE, config.TTS_RATE)
                    vo_dur = get_audio_duration(vo_audio)
                except Exception as e:
                    print(f"      [WARN] TTS gagal: {e}")
                    vo_audio, vo_dur = "", 0.0

                comp_vo_data = {
                    "intro_audio":    vo_audio,
                    "intro_duration": vo_dur,
                    "intro_text":     narration,
                    "hook_text":      hook_text,
                }

                # ── Buat intro card untuk compilation ini ───────────
                comp_intro = create_intro_video(
                    clip_dir=intro_dir,
                    thumbnail_path=primary_meta.get("thumbnail_path", ""),
                    voiceover_data=comp_vo_data,
                    hook_text=hook_text,
                    logo_path=config.LOGO_PATH,
                    logo_size=config.LOGO_SIZE,
                    logo_position=config.LOGO_POSITION,
                    logo_opacity=config.LOGO_OPACITY,
                    res_w=res_w, res_h=res_h,
                )

                comp_path = os.path.join(comp_dir, f"COMPILATION_{gi:02d}.mp4")
                ok = create_compilation(
                    segments=group,
                    output_path=comp_path,
                    intro_path=comp_intro,
                    res_w=res_w, res_h=res_h,
                )
                if ok:
                    print(f"    ✅ Compilation {gi:02d} selesai: {comp_path}")
                else:
                    print(f"    [WARNING] Compilation {gi:02d} gagal dibuat")

    # ═════════════════════════════════════════════════════
    # STEP 6: Review Package
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("📋 STEP 6: Membuat Review Package")
    print("=" * 60)

    generate_review_package(session_dir, videos_meta, clips_data, final_clips, context)

    # ═════════════════════════════════════════════════════
    # DONE
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("✅ SELESAI!")
    print("=" * 60)
    print(f"\n📁 Folder hasil : {os.path.abspath(session_dir)}")
    print(f"📋 Review checklist : {os.path.join(os.path.abspath(session_dir), 'REVIEW_CHECKLIST.md')}")
    if combine:
        print(f"🎞️  Compilations    : {os.path.join(os.path.abspath(session_dir), 'compilations/')}")
    print(f"🎬 Total clips      : {len(final_clips)}")
    print(f"\n💡 LANGKAH SELANJUTNYA:")
    print(f"   1. Tonton tiap clip di folder clips/")
    print(f"   2. (Opsional) Rekam ulang voiceover dengan suara sendiri")
    print(f"   3. Tambah logo/watermark jika belum")
    print(f"   4. Buat thumbnail custom")
    print(f"   5. Edit judul & deskripsi di REVIEW_CHECKLIST.md")
    print(f"   6. Upload manual ke YouTube (maks 2-3/hari)")


def generate_review_package(session_dir: str, videos_meta: list,
                            clips_data: list, final_clips: list,
                            context: str = ""):
    """Generate markdown review checklist."""
    checklist_path = os.path.join(session_dir, "REVIEW_CHECKLIST.md")

    lines = [
        "# 📋 Review Checklist - YouTube Clipper",
        "",
    ]

    if len(videos_meta) > 1:
        lines += ["## Video Sumber", ""]
        for vm in videos_meta:
            lines.append(f"- **Video {vm.get('source_index', '?')}:** [{vm.get('title', '?')}]({vm.get('url', '')})")
        lines.append("")
    else:
        vm = videos_meta[0]
        lines += [
            f"**Video Asli:** {vm.get('title', 'Unknown')}",
            f"**Channel:** {vm.get('channel', 'Unknown')}",
            f"**URL:** {vm.get('url', '')}",
        ]

    if context:
        lines.append(f"**Context:** {context}")

    lines += [
        f"**Generate:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Clips",
        "",
    ]

    for clip in clips_data:
        num = clip["clip_number"]
        duration = clip["end_time"] - clip["start_time"]
        src = clip.get("source_video", "")
        src_label = f" (Video {src})" if src and len(videos_meta) > 1 else ""

        lines += [
            f"### Clip #{num}{src_label}: {clip['title']}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Durasi | {duration:.0f} detik |",
            f"| Viral Score | {clip.get('viral_score', '?')}/10 |",
            f"| File | `clips/clip_{num:02d}/FINAL_clip_{num:02d}.mp4` |",
            "",
            f"**Poin Utama:**",
            f"> {clip.get('key_point', '')}",
            "",
            f"**Draft Judul:**",
            f"> {clip['title']}",
            "",
            f"**Hook (3 detik pertama):**",
            f"> {clip.get('hook', '')}",
            "",
            f"**Commentary Intro** *(AI draft — ganti dengan voiceover sendiri)*:",
            f"> {clip.get('commentary_intro', '')}",
            "",
            f"**Commentary Outro:**",
            f"> {clip.get('commentary_outro', '')}",
            "",
            f"**Tags:** `{'` `'.join(clip.get('tags', []))}`",
            "",
            "**Checklist sebelum upload:**",
            "- [ ] Tonton clip — potongan natural di awal & akhir?",
            "- [ ] Subtitle akurat? Koreksi nama/istilah yang salah",
            "- [ ] Intro: thumbnail + hook text menarik?",
            "- [ ] Outro: CTA text terlihat jelas?",
            "- [ ] (Opsional) Rekam voiceover sendiri untuk intro & outro",
            "- [ ] Buat thumbnail custom",
            "- [ ] Finalisasi judul",
            "- [ ] Tulis deskripsi + credit channel asli",
            "",
            "**Status:** ⬜ Belum | 🟡 Perlu Edit | ✅ Siap Upload",
            "",
            "---",
            "",
        ]

    lines += [
        "## 💡 Tips Sentuhan Personal",
        "",
        "1. **Voiceover** — AI voiceover cukup untuk draft. Rekam ulang dengan suara sendiri untuk hasil lebih personal.",
        "2. **Thumbnail** — Buat custom dengan Canva/Photoshop. Jangan pakai frame video mentah.",
        "3. **Judul** — Buat curiosity gap. Jangan sama persis dengan video asli.",
        "4. **Deskripsi** — Selalu cantumkan credit channel asli + link video sumber.",
        "5. **Upload** — Maksimal 2-3 clip/hari. Bulk upload memicu review manual YouTube.",
        "",
        "## ⚙️ Config yang Dipakai",
        "",
        f"- TTS Voice: `{config.TTS_VOICE}`",
        f"- Outro CTA: `{config.OUTRO_CTA_TEXT}`",
        f"- Logo: `{config.LOGO_PATH or '(tidak ada)'}`",
        f"- Format: `{config.CLIP_FORMAT}` ({config.CLIP_MIN_DURATION}-{config.CLIP_MAX_DURATION}s)",
    ]

    with open(checklist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"    Review checklist: {checklist_path}")

    # Save session metadata
    meta_path = os.path.join(session_dir, "session_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "videos": videos_meta,
            "context": context,
            "clips_count": len(clips_data),
            "clips": clips_data,
            "generated_at": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)


def get_api_key() -> str:
    if config.LLM_PROVIDER == "openai":
        return config.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
    elif config.LLM_PROVIDER == "anthropic":
        return config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    return ""


def print_banner():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║    🎬  YOUTUBE AUTO CLIPPER  v2                               ║
║                                                               ║
║    Single video:                                              ║
║      python clipper.py <url>                                  ║
║                                                               ║
║    Multi video → clip terpisah:                               ║
║      python clipper.py <url1> <url2> <url3>                   ║
║                                                               ║
║    Multi video → 1 compilation video:                         ║
║      python clipper.py <url1> <url2> --combine                ║
║                                                               ║
║    Dengan context:                                            ║
║      python clipper.py <url> --context "momen lucu"           ║
║      python clipper.py <url1> <url2> --combine \\             ║
║        --context "highlight lucu dari semua video"            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
