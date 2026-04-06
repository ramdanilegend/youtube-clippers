"""
Module 5: Video Editor
Menggunakan FFmpeg untuk memotong clip, menambah subtitle, voiceover,
hook text overlay, logo, dan intro/outro dengan thumbnail background.
"""

import os
import json
import re
import subprocess
import shutil

# Common stop words to skip when identifying keywords (EN + ID)
_STOPWORDS = {
    'the','a','an','is','are','was','were','be','been','being','have','has',
    'had','do','does','did','will','would','shall','should','may','might',
    'must','can','could','to','of','in','on','at','by','for','with','about',
    'and','but','or','so','not','i','you','he','she','it','we','they','this',
    'that','my','your','his','her','its','our','their','what','if','as',
    'just','also','very','up','out','then','than','more','all','get','got',
    # Indonesian
    'dan','yang','di','ke','dari','ada','ini','itu','dengan','untuk','pada',
    'dalam','adalah','juga','bisa','akan','kita','saya','anda','dia','mereka',
    'kami','tidak','sudah','agar','jika','atau','tapi','lebih','sangat','oleh',
    'ya','kan','nya','lah','kah','pun','si','itu','hal','cara'
}


def create_clip(video_path: str, clip_data: dict, voiceover_data: dict,
                transcript_segments: list, output_dir: str,
                thumbnail_path: str = "",
                clip_format: str = "vertical",
                subtitle_font_size: int = 42,
                subtitle_color: str = "white",
                subtitle_bg: str = "black@0.6",
                brand_text: str = "",
                brand_position: str = "top-right",
                logo_path: str = "",
                logo_size: int = 120,
                logo_position: str = "top-left",
                logo_opacity: float = 0.8,
                outro_cta_text: str = "",
                outro_duration: float = 4.0,
                compile_mode: bool = False) -> str:
    """
    Buat satu clip lengkap dengan:
    - Intro: thumbnail blur + voiceover + hook text + logo
    - Video terpotong + subtitle + branding
    - Outro: thumbnail blur + voiceover + CTA text + logo
    """
    clip_num = clip_data["clip_number"]
    start = clip_data["start_time"]
    end = clip_data["end_time"]
    hook_text = voiceover_data.get("hook_text", "")

    clip_dir = os.path.join(output_dir, f"clip_{clip_num:02d}")
    os.makedirs(clip_dir, exist_ok=True)

    # Determine resolution
    if clip_format == "vertical":
        res_w, res_h = 1080, 1920
    else:
        res_w, res_h = 1920, 1080

    print(f"\n[Editor] Membuat Clip #{clip_num}: {clip_data['title']}")

    # ─── Step 1: Potong video ──────────────────────────────
    raw_clip = os.path.join(clip_dir, "raw.mp4")
    print(f"    [1/6] Memotong video ({start:.1f}s - {end:.1f}s)...")
    cut_cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(end - start),
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-avoid_negative_ts", "make_zero",
        raw_clip
    ]
    r = subprocess.run(cut_cmd, capture_output=True, text=True)
    if not os.path.exists(raw_clip) or os.path.getsize(raw_clip) < 1000:
        print(f"    [ERROR] Gagal memotong video: {r.stderr[-300:]}")
        return ""

    # ─── Step 2: Crop ke format ───────────────────────────
    cropped_clip = os.path.join(clip_dir, "cropped.mp4")
    print(f"    [2/6] Cropping ke format {'vertical (9:16)' if clip_format == 'vertical' else 'horizontal (16:9)'}...")
    if clip_format == "vertical":
        crop_cmd = [
            "ffmpeg", "-y", "-i", raw_clip,
            "-vf", f"crop=ih*9/16:ih,scale={res_w}:{res_h}",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            cropped_clip
        ]
    else:
        crop_cmd = [
            "ffmpeg", "-y", "-i", raw_clip,
            "-vf", f"scale={res_w}:{res_h}:force_original_aspect_ratio=decrease,pad={res_w}:{res_h}:-1:-1",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            cropped_clip
        ]
    r = subprocess.run(crop_cmd, capture_output=True, text=True)
    if not os.path.exists(cropped_clip) or os.path.getsize(cropped_clip) < 1000:
        # Fallback: copy raw_clip as cropped (skip spatial crop)
        print(f"    [WARNING] Crop gagal, menggunakan raw clip sebagai fallback...")
        print(f"    [DEBUG] FFmpeg error: {r.stderr[-300:]}")
        import shutil as _shutil
        _shutil.copy2(raw_clip, cropped_clip)

    # ─── Step 3: Build subtitle chunks ────────────────────
    print("    [3/6] Membuat subtitle chunks...")
    is_vertical = clip_format == "vertical"
    sub_font    = subtitle_font_size if subtitle_font_size else (54 if is_vertical else 46)
    sub_margin  = 260 if is_vertical else 90
    sub_chunks  = _build_subtitle_chunks(transcript_segments, start, end)
    print(f"          {len(sub_chunks)} subtitle chunk(s) dibuat")

    # ─── Step 4: Burn subtitle + branding (Pillow + FFmpeg overlay) ────
    print("    [4/6] Membakar subtitle ke video...")
    styled_clip = os.path.join(clip_dir, "styled.mp4")
    burned = _burn_subtitles_to_clip(
        chunks=sub_chunks,
        clip_dur=end - start,
        main_clip=cropped_clip,
        output_clip=styled_clip,
        res_w=res_w, res_h=res_h,
        font_size=sub_font,
        margin_v=sub_margin,
        work_dir=clip_dir,
        brand_text=brand_text,
        brand_position=brand_position,
    )
    if not burned:
        print("    [WARNING] Subtitle burn gagal, menggunakan clip tanpa subtitle...")
        if os.path.exists(cropped_clip):
            styled_clip = cropped_clip
        elif os.path.exists(raw_clip):
            styled_clip = raw_clip
        else:
            print(f"    [ERROR] Tidak ada clip yang bisa digunakan untuk clip #{clip_num}")
            return ""

    # ─── compile_mode: return styled clip only (no intro/merge) ──────────
    if compile_mode:
        for temp in [raw_clip, cropped_clip]:
            if os.path.exists(temp) and temp != styled_clip:
                safe_remove(temp)
        print(f"    Segment #{clip_num} siap: {styled_clip}")
        return styled_clip

    # ─── Step 5: Buat intro video ─────────────────────────
    print("    [5/6] Membuat intro dengan creative card...")
    intro_video = create_intro_video(
        clip_dir=clip_dir,
        thumbnail_path=thumbnail_path,
        voiceover_data=voiceover_data,
        hook_text=hook_text,
        logo_path=logo_path,
        logo_size=logo_size,
        logo_position=logo_position,
        logo_opacity=logo_opacity,
        res_w=res_w, res_h=res_h
    )

    # ─── Step 6: Merge intro + clip ────────────────────────
    print("    [6/6] Menggabungkan semua bagian...")
    final_clip = os.path.join(clip_dir, f"FINAL_clip_{clip_num:02d}.mp4")
    merge_parts(intro_video, styled_clip, "", final_clip)

    # Cleanup
    for temp in [raw_clip, cropped_clip]:
        if os.path.exists(temp) and temp != styled_clip:
            safe_remove(temp)

    print(f"    Clip #{clip_num} selesai: {final_clip}")
    return final_clip


def _render_intro_card(hook_text: str, intro_text: str,
                       thumbnail_path: str,
                       res_w: int, res_h: int,
                       output_png: str) -> bool:
    """
    Render a creative intro card as a full-resolution PNG using Pillow.

    Layout (top → bottom):
      • Blurred/darkened thumbnail background (or dark gradient)
      • Vignette overlay (dark edges)
      • Yellow accent bar at top
      • "● VIRAL CLIP" badge
      • Hook text — large, bold, word-level color (yellow = keyword, white = normal)
      • Thin divider line
      • Intro commentary text — medium, white, word-wrapped
      • Bottom hint arrow
    """
    from PIL import Image, ImageDraw, ImageFilter

    # ── Background ────────────────────────────────────────────────────────
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            bg = Image.open(thumbnail_path).convert("RGB")
            ratio = max(res_w / bg.width, res_h / bg.height)
            new_w = int(bg.width * ratio)
            new_h = int(bg.height * ratio)
            bg = bg.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - res_w) // 2
            top  = (new_h - res_h) // 2
            bg   = bg.crop((left, top, left + res_w, top + res_h))
            bg   = bg.filter(ImageFilter.GaussianBlur(radius=28))
            bg   = bg.point(lambda p: int(p * 0.28))   # heavy darken
        except Exception:
            bg = Image.new("RGB", (res_w, res_h), (10, 10, 22))
    else:
        bg = Image.new("RGB", (res_w, res_h), (10, 10, 22))

    card = bg.convert("RGBA")

    # ── Vignette overlay ──────────────────────────────────────────────────
    vig = Image.new("RGBA", (res_w, res_h), (0, 0, 0, 0))
    dv  = ImageDraw.Draw(vig)
    # Top 45% gradient (dark → transparent)
    for y in range(int(res_h * 0.45)):
        a = int(200 * (1 - y / (res_h * 0.45)))
        dv.line([(0, y), (res_w, y)], fill=(0, 0, 0, a))
    # Bottom 45% gradient (transparent → dark)
    for y in range(int(res_h * 0.55), res_h):
        a = int(200 * (y - res_h * 0.55) / (res_h * 0.45))
        dv.line([(0, y), (res_w, y)], fill=(0, 0, 0, a))
    card = Image.alpha_composite(card, vig)

    draw = ImageDraw.Draw(card)

    # ── Fonts ─────────────────────────────────────────────────────────────
    font_hook    = _load_subtitle_font(76)   # large bold hook
    font_body    = _load_subtitle_font(38)   # intro commentary
    font_badge   = _load_subtitle_font(28)   # badge text
    font_arrow   = _load_subtitle_font(48)   # bottom arrow hint

    PAD = 60   # horizontal padding

    # ── Yellow accent bar (top) ───────────────────────────────────────────
    bar_y = 72
    draw.rectangle([(0, bar_y), (res_w, bar_y + 7)], fill=(255, 210, 0, 255))

    # ── "● VIRAL CLIP" badge ──────────────────────────────────────────────
    badge_text = "● VIRAL CLIP"
    badge_y    = bar_y + 26
    try:
        bb = draw.textbbox((0, 0), badge_text, font=font_badge)
        bw = bb[2] - bb[0] + 28
        bh = bb[3] - bb[1] + 14
    except Exception:
        bw, bh = 160, 40
    bx = PAD
    draw.rounded_rectangle([(bx, badge_y), (bx + bw, badge_y + bh)],
                            radius=8, fill=(255, 30, 30, 220))
    draw.text((bx + 14, badge_y + 7), badge_text, font=font_badge,
              fill=(255, 255, 255, 255))

    # ── Hook text (word-level keyword highlight) ──────────────────────────
    # Wrap into lines of max ~4 words each
    hook_words = (hook_text or "").split()
    words_per_line = 4
    hook_lines = [hook_words[i:i + words_per_line]
                  for i in range(0, len(hook_words), words_per_line)]

    # Measure total hook block height to center it vertically (~38-55% from top)
    line_h = int(76 * 1.35)
    total_hook_h = len(hook_lines) * line_h
    hook_start_y = int(res_h * 0.30) - total_hook_h // 2

    outline_px = 4

    def draw_word_row(words_in_line, y):
        """Draw one row of words with per-word keyword coloring, centered."""
        # Pre-measure each word to find total line width
        parts = []
        space_w = 18
        total_w = 0
        for idx, wd in enumerate(words_in_line):
            try:
                wb = draw.textbbox((0, 0), wd, font=font_hook)
                ww = wb[2] - wb[0]
            except Exception:
                ww = len(wd) * 38
            parts.append((wd, ww, _is_keyword(wd)))
            total_w += ww
            if idx < len(words_in_line) - 1:
                total_w += space_w

        x = (res_w - total_w) // 2
        for wd, ww, is_kw in parts:
            fg = (255, 215, 0, 255) if is_kw else (255, 255, 255, 255)
            # Black outline
            for dx in range(-outline_px, outline_px + 1):
                for dy in range(-outline_px, outline_px + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), wd, font=font_hook,
                                  fill=(0, 0, 0, 255))
            # Drop shadow
            draw.text((x + 3, y + 4), wd, font=font_hook, fill=(0, 0, 0, 180))
            # Main word
            draw.text((x, y), wd, font=font_hook, fill=fg)
            x += ww + space_w

    for li, line_words in enumerate(hook_lines):
        draw_word_row(line_words, hook_start_y + li * line_h)

    # ── Divider line ──────────────────────────────────────────────────────
    div_y = hook_start_y + total_hook_h + 28
    div_pad = 120
    draw.line([(div_pad, div_y), (res_w - div_pad, div_y)],
              fill=(255, 210, 0, 180), width=3)

    # ── Intro commentary text (word-wrapped) ──────────────────────────────
    body_text = (intro_text or "").strip()
    if body_text:
        body_words = body_text.split()
        # Wrap to fit within (res_w - 2*PAD) width
        max_line_w = res_w - PAD * 2
        body_lines = []
        current_line = []
        current_w    = 0
        sp_w = 14
        for wd in body_words:
            try:
                wb = draw.textbbox((0, 0), wd, font=font_body)
                ww = wb[2] - wb[0]
            except Exception:
                ww = len(wd) * 18
            if current_line and current_w + sp_w + ww > max_line_w:
                body_lines.append(" ".join(current_line))
                current_line = [wd]
                current_w    = ww
            else:
                current_line.append(wd)
                current_w += (sp_w if current_line else 0) + ww
        if current_line:
            body_lines.append(" ".join(current_line))

        body_line_h = int(38 * 1.45)
        body_y      = div_y + 36
        for ln in body_lines[:5]:     # cap at 5 lines
            try:
                lb = draw.textbbox((0, 0), ln, font=font_body)
                lw = lb[2] - lb[0]
            except Exception:
                lw = len(ln) * 18
            lx = (res_w - lw) // 2
            # Soft shadow
            draw.text((lx + 2, body_y + 2), ln, font=font_body,
                      fill=(0, 0, 0, 160))
            draw.text((lx, body_y), ln, font=font_body,
                      fill=(220, 220, 220, 255))
            body_y += body_line_h

    # ── Bottom hint arrow ─────────────────────────────────────────────────
    arrow = "▼"
    try:
        ab = draw.textbbox((0, 0), arrow, font=font_arrow)
        aw = ab[2] - ab[0]
    except Exception:
        aw = 40
    ax = (res_w - aw) // 2
    ay = res_h - 200
    draw.text((ax, ay), arrow, font=font_arrow, fill=(255, 210, 0, 200))

    # ── Save ──────────────────────────────────────────────────────────────
    card.convert("RGB").save(output_png, "PNG")
    return os.path.exists(output_png) and os.path.getsize(output_png) > 100


def create_intro_video(clip_dir: str, thumbnail_path: str,
                       voiceover_data: dict, hook_text: str,
                       logo_path: str, logo_size: int,
                       logo_position: str, logo_opacity: float,
                       res_w: int, res_h: int) -> str:
    """
    Buat video intro dengan creative Pillow-rendered card:
    - Background: thumbnail (heavy blur + darken) atau dark gradient
    - Hook text besar dengan keyword highlight kuning (word-level)
    - Intro commentary text di bawah hook
    - Audio: TTS voiceover intro
    - Logo overlay (opsional)
    """
    intro_audio    = voiceover_data.get("intro_audio", "")
    intro_duration = voiceover_data.get("intro_duration", 0)
    intro_text     = voiceover_data.get("intro_text", "")

    if not intro_audio or not os.path.exists(intro_audio) or intro_duration <= 0:
        return ""

    intro_path = os.path.join(clip_dir, "intro.mp4")

    # ── Step 1: Render intro card PNG with Pillow ─────────────────────────
    card_png = os.path.join(clip_dir, "intro_card.png")
    card_ok  = _render_intro_card(
        hook_text=hook_text,
        intro_text=intro_text,
        thumbnail_path=thumbnail_path,
        res_w=res_w, res_h=res_h,
        output_png=card_png,
    )

    # ── Step 2: Compose intro video (loop card PNG + audio) ───────────────
    if card_ok:
        input_args = ["-loop", "1", "-i", card_png]
        vf_string  = "null"   # PNG already fully rendered
    else:
        # Fallback: plain dark background
        input_args = ["-f", "lavfi",
                      "-i", f"color=c=0x0d0d1a:s={res_w}x{res_h}:d={intro_duration + 1}:r=30"]
        vf_string  = "null"

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-i", intro_audio,
        "-vf", vf_string,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(intro_duration + 0.5),
        "-shortest",
        "-pix_fmt", "yuv420p",
        intro_path
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(intro_path) and os.path.getsize(intro_path) > 1000:
        # Add logo overlay if specified
        if logo_path and os.path.exists(logo_path):
            with_logo = os.path.join(clip_dir, "intro_logo.mp4")
            if overlay_logo(intro_path, logo_path, with_logo,
                            logo_size, logo_position, logo_opacity):
                safe_remove(intro_path)
                os.rename(with_logo, intro_path)
        return intro_path

    return ""


def create_outro_video(clip_dir: str, thumbnail_path: str,
                       voiceover_data: dict, cta_text: str,
                       logo_path: str, logo_size: int,
                       logo_position: str, logo_opacity: float,
                       outro_duration: float,
                       res_w: int, res_h: int) -> str:
    """
    Buat video outro:
    - Background: thumbnail (blur + darken)
    - Audio: TTS outro commentary + CTA
    - Text: outro text + CTA (subscribe dll)
    - Logo overlay
    """
    outro_audio = voiceover_data.get("outro_audio", "")
    outro_dur = voiceover_data.get("outro_duration", 0)
    cta_audio = voiceover_data.get("cta_audio", "")
    cta_dur = voiceover_data.get("cta_duration", 0)
    outro_text = voiceover_data.get("outro_text", "")

    # Gabung outro audio + CTA audio jadi satu
    combined_audio = ""
    total_duration = 0

    if outro_audio and os.path.exists(outro_audio):
        if cta_audio and os.path.exists(cta_audio):
            # Merge kedua audio
            combined_audio = os.path.join(clip_dir, "outro_combined.mp3")
            concat_file = os.path.join(clip_dir, "outro_audio_list.txt")
            with open(concat_file, "w") as f:
                f.write(f"file '{os.path.abspath(outro_audio)}'\n")
                f.write(f"file '{os.path.abspath(cta_audio)}'\n")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_file, "-c:a", "aac", "-b:a", "128k",
                combined_audio
            ], capture_output=True)
            safe_remove(concat_file)
            total_duration = outro_dur + cta_dur
        else:
            combined_audio = outro_audio
            total_duration = outro_dur
    elif cta_audio and os.path.exists(cta_audio):
        combined_audio = cta_audio
        total_duration = cta_dur

    if not combined_audio or total_duration <= 0:
        # No audio at all — buat short CTA card jika ada CTA text
        if cta_text:
            total_duration = outro_duration
        else:
            return ""

    outro_path = os.path.join(clip_dir, "outro.mp4")

    # Build video filter
    vf_parts = []

    if thumbnail_path and os.path.exists(thumbnail_path):
        bg_filter = f"scale={res_w}:{res_h}:force_original_aspect_ratio=increase,crop={res_w}:{res_h},gblur=sigma=25,eq=brightness=-0.4"
        input_args = ["-loop", "1", "-i", thumbnail_path]
    else:
        bg_filter = "null"
        input_args = ["-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={res_w}x{res_h}:d={total_duration + 1}:r=30"]

    vf_parts.append(bg_filter)

    # Outro commentary text
    if outro_text and len(outro_text) < 150:
        safe_outro = escape_ffmpeg_text(outro_text[:120])
        vf_parts.append(
            f"drawtext=text='{safe_outro}'"
            f":fontsize=32:fontcolor=white"
            f":x=(w-text_w)/2:y=(h/2)-80"
            f":box=1:boxcolor=black@0.6:boxborderw=15"
        )

    # CTA text (bigger, more prominent)
    if cta_text:
        safe_cta = escape_ffmpeg_text(cta_text)
        vf_parts.append(
            f"drawtext=text='{safe_cta}'"
            f":fontsize=40:fontcolor=yellow"
            f":x=(w-text_w)/2:y=(h/2)+40"
            f":box=1:boxcolor=red@0.8:boxborderw=18"
        )

    vf_string = ",".join(vf_parts) if vf_parts else "null"

    cmd = ["ffmpeg", "-y", *input_args]

    if combined_audio and os.path.exists(combined_audio):
        cmd.extend(["-i", combined_audio])

    cmd.extend([
        "-vf", vf_string,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(total_duration + 0.5),
        "-shortest",
        "-pix_fmt", "yuv420p",
        outro_path
    ])
    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(outro_path) and os.path.getsize(outro_path) > 1000:
        # Add logo
        if logo_path and os.path.exists(logo_path):
            with_logo = os.path.join(clip_dir, "outro_logo.mp4")
            if overlay_logo(outro_path, logo_path, with_logo,
                          logo_size, logo_position, logo_opacity):
                safe_remove(outro_path)
                os.rename(with_logo, outro_path)
        return outro_path

    return ""


def overlay_logo(video_path: str, logo_path: str, output_path: str,
                 logo_size: int = 120, position: str = "top-left",
                 opacity: float = 0.8) -> bool:
    """Overlay logo PNG di atas video."""
    pos_map = {
        "top-left": f"x=20:y=20",
        "top-right": f"x=main_w-overlay_w-20:y=20",
        "bottom-left": f"x=20:y=main_h-overlay_h-20",
        "bottom-right": f"x=main_w-overlay_w-20:y=main_h-overlay_h-20",
    }
    pos = pos_map.get(position, pos_map["top-left"])

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex",
        f"[1:v]scale={logo_size}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
        f"[0:v][logo]overlay={pos}[out]",
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def _create_title_card(title: str, source_label: str,
                       output_path: str,
                       res_w: int = 1080, res_h: int = 1920,
                       duration: float = 1.8) -> bool:
    """
    Render a short title-card video (Pillow PNG → FFmpeg loop).
    Shown between segments in --combine compilation.
    Design: black background, large bold title with keyword highlight, source label.
    """
    from PIL import Image, ImageDraw

    card = Image.new("RGB", (res_w, res_h), (8, 8, 12))
    draw = ImageDraw.Draw(card)

    font_title  = _load_subtitle_font(68)
    font_source = _load_subtitle_font(30)
    PAD = 70

    # Yellow left accent bar
    draw.rectangle([(PAD, res_h // 2 - 160), (PAD + 6, res_h // 2 + 160)],
                   fill=(255, 210, 0))

    # Title words with keyword highlight (word-by-word, centered block)
    title_words = (title or "").split()
    words_per_line = 4
    title_lines = [title_words[i:i + words_per_line]
                   for i in range(0, len(title_words), words_per_line)]

    line_h = int(68 * 1.4)
    total_h = len(title_lines) * line_h
    start_y = res_h // 2 - total_h // 2 - 30
    outline  = 3

    for li, line_words in enumerate(title_lines):
        # Measure total line width
        parts, total_w, sp_w = [], 0, 16
        for idx, wd in enumerate(line_words):
            try:
                wb = draw.textbbox((0, 0), wd, font=font_title)
                ww = wb[2] - wb[0]
            except Exception:
                ww = len(wd) * 32
            parts.append((wd, ww, _is_keyword(wd)))
            total_w += ww + (sp_w if idx < len(line_words) - 1 else 0)

        x = (res_w - total_w) // 2
        y = start_y + li * line_h
        for wd, ww, is_kw in parts:
            fg = (255, 215, 0) if is_kw else (255, 255, 255)
            for dx in range(-outline, outline + 1):
                for dy in range(-outline, outline + 1):
                    if dx or dy:
                        draw.text((x + dx, y + dy), wd, font=font_title,
                                  fill=(0, 0, 0))
            draw.text((x, y), wd, font=font_title, fill=fg)
            x += ww + sp_w

    # Source label
    if source_label:
        try:
            sb = draw.textbbox((0, 0), source_label, font=font_source)
            sw = sb[2] - sb[0]
        except Exception:
            sw = len(source_label) * 15
        draw.text(((res_w - sw) // 2, start_y + total_h + 24),
                  source_label, font=font_source, fill=(160, 160, 160))

    # Save PNG
    png_path = output_path.replace(".mp4", "_card.png")
    card.save(png_path, "PNG")

    # PNG → short silent video
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k",
        "-t", str(duration),
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 500


def concat_clips(paths: list, output_path: str) -> bool:
    """
    Encode all clips to a uniform format then concatenate into output_path.
    Handles N clips (generalised version of merge_parts).
    Returns True on success.
    """
    if not paths:
        return False
    if len(paths) == 1:
        shutil.copy2(paths[0], output_path)
        return True

    work_dir   = os.path.dirname(output_path)
    temp_files = []
    normalized = []

    for i, part in enumerate(paths):
        if not part or not os.path.exists(part):
            continue
        norm = os.path.join(work_dir, f"_norm_{i}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", part,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100", "-ac", "2", "-r", "30",
            "-pix_fmt", "yuv420p",
            norm
        ]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(norm) and os.path.getsize(norm) > 500:
            normalized.append(norm)
            temp_files.append(norm)
        else:
            normalized.append(part)

    concat_txt = output_path + "_list.txt"
    with open(concat_txt, "w") as f:
        for p in normalized:
            f.write(f"file '{os.path.abspath(p)}'\n")
    temp_files.append(concat_txt)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(cmd, capture_output=True)

    for f in temp_files:
        safe_remove(f)

    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def create_compilation(segments: list, output_path: str,
                       intro_path: str = "",
                       res_w: int = 1080, res_h: int = 1920) -> bool:
    """
    Gabungkan segment clips menjadi satu video compilation (mode --combine).

    segments: list of {
        "path": str,        # path to burned-subtitle styled.mp4
        "title": str,       # clip title (for title card)
        "source": str,      # source channel label
        "clip_number": int
    }

    Structure of final output:
      [intro] → [title card 1] → [segment 1] → [title card 2] → [segment 2] → ...
    """
    work_dir = os.path.dirname(output_path)
    parts    = []
    temps    = []

    if intro_path and os.path.exists(intro_path):
        parts.append(intro_path)

    for i, seg in enumerate(segments):
        seg_path = seg.get("path", "")
        if not seg_path or not os.path.exists(seg_path):
            print(f"    [WARN] Segment {seg.get('clip_number','?')} tidak ditemukan, dilewati")
            continue

        # Title card
        tc_path = os.path.join(work_dir, f"_tc_{i:03d}.mp4")
        if _create_title_card(
            title=seg.get("title", ""),
            source_label=seg.get("source", ""),
            output_path=tc_path,
            res_w=res_w, res_h=res_h,
            duration=1.8
        ):
            parts.append(tc_path)
            temps.append(tc_path)

        parts.append(seg_path)

    if not parts:
        return False

    ok = concat_clips(parts, output_path)

    for t in temps:
        safe_remove(t)

    return ok


def merge_parts(intro_path: str, main_path: str, outro_path: str,
                output_path: str):
    """Merge intro + main clip + outro menggunakan concat_clips."""
    parts = []
    if intro_path and os.path.exists(intro_path):
        parts.append(intro_path)
    parts.append(main_path)
    if outro_path and os.path.exists(outro_path):
        parts.append(outro_path)
    concat_clips(parts, output_path)


def _ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _is_keyword(word: str) -> bool:
    """Return True if this word should be highlighted yellow."""
    clean = re.sub(r"[^\w]", "", word).lower()
    if not clean:
        return False
    # Numbers / percentages / stats always highlighted
    if re.match(r"^\d+([.,]\d+)?%?$", clean):
        return True
    # ALL-CAPS emphasis words
    if word.isupper() and len(word) > 1:
        return True
    # Long meaningful words not in stoplist
    if len(clean) >= 6 and clean not in _STOPWORDS:
        return True
    return False


def _escape_ass(text: str) -> str:
    """Escape literal braces and backslashes in ASS dialogue text."""
    text = text.replace("\\", "\\\\ ")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text


def _ass_word(word: str) -> str:
    """Return ASS-formatted word, highlighted yellow if it's a keyword."""
    escaped = _escape_ass(word)
    if _is_keyword(word):
        # Yellow = &H0000FFFF in ASS AABBGGRR format
        return f"{{\\c&H0000FFFF&}}{escaped}{{\\r}}"
    return escaped


def generate_ass(segments: list, clip_start: float, clip_end: float,
                 output_path: str, res_w: int = 1080, res_h: int = 1920,
                 font_size: int = None) -> str:
    """
    Generate a burned-in ASS subtitle file:
    - Bold white text with black outline + shadow
    - Bottom-center, safe margin above YouTube Shorts UI
    - Word-level sync (3-word chunks) when word timestamps available
    - Key words highlighted in yellow
    """
    is_vertical = res_h > res_w
    if font_size is None:
        font_size = 54 if is_vertical else 46
    # Safe bottom margin: YouTube Shorts UI occupies ~200-250px at 1920px height
    margin_v = 260 if is_vertical else 90

    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {res_w}
PlayResY: {res_h}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    clip_dur = clip_end - clip_start

    for seg in segments:
        if seg["end"] < clip_start or seg["start"] > clip_end:
            continue

        adj_start = max(0.0, seg["start"] - clip_start)
        adj_end = min(clip_dur, seg["end"] - clip_start)
        if adj_end <= adj_start:
            continue

        words = seg.get("words", [])

        if words:
            # ── Word-level: group into 3-word chunks ──────────────
            # Filter words to the clip window and adjust timestamps
            clip_words = []
            for w in words:
                ws = max(0.0, w["start"] - clip_start)
                we = min(clip_dur, w["end"] - clip_start)
                if we > 0 and ws < clip_dur and w["word"]:
                    clip_words.append({"start": ws, "end": we,
                                       "word": w["word"]})

            chunk_size = 3
            for i in range(0, len(clip_words), chunk_size):
                chunk = clip_words[i:i + chunk_size]
                if not chunk:
                    continue
                c_start = chunk[0]["start"]
                c_end = chunk[-1]["end"]
                # Ensure minimum display time of 0.3 s
                if c_end - c_start < 0.3:
                    c_end = c_start + 0.3
                text = " ".join(_ass_word(w["word"]) for w in chunk)
                events.append(
                    f"Dialogue: 0,{_ass_time(c_start)},{_ass_time(c_end)},"
                    f"Default,,0,0,0,,{text}"
                )
        else:
            # ── Segment-level fallback (no word timestamps) ────────
            raw_words = seg["text"].split()
            per_line = 4  # words per subtitle line
            lines = []
            for i in range(0, len(raw_words), per_line):
                chunk = raw_words[i:i + per_line]
                lines.append(" ".join(_ass_word(w) for w in chunk))
            text = "\\N".join(lines)
            events.append(
                f"Dialogue: 0,{_ass_time(adj_start)},{_ass_time(adj_end)},"
                f"Default,,0,0,0,,{text}"
            )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    return output_path


def _load_subtitle_font(size: int):
    """Find and load the best available bold/heavy font for subtitle rendering."""
    from PIL import ImageFont
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",               # macOS – heavy
        "/Library/Fonts/Arial Bold.ttf",                                # macOS + Office
        "/System/Library/Fonts/HelveticaNeue.ttc",                      # macOS
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",        # Linux
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",         # Linux
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception:
        return ImageFont.load_default()


def _build_subtitle_chunks(segments: list, clip_start: float,
                            clip_end: float) -> list:
    """
    Convert transcript segments into timed subtitle chunks.
    Returns list of {"text", "start", "end", "has_kw"}.
    """
    chunks   = []
    clip_dur = clip_end - clip_start

    for seg in segments:
        if seg["end"] < clip_start or seg["start"] > clip_end:
            continue

        adj_start = max(0.0, seg["start"] - clip_start)
        adj_end   = min(clip_dur, seg["end"] - clip_start)
        if adj_end <= adj_start:
            continue

        raw_words = seg.get("words", [])

        if raw_words:
            # ── Word-level: 3-word chunks with Whisper timestamps ─────
            clip_words = []
            for w in raw_words:
                ws = max(0.0, w["start"] - clip_start)
                we = min(clip_dur, w["end"] - clip_start)
                if we > 0 and ws < clip_dur and w.get("word"):
                    clip_words.append({"start": ws, "end": we,
                                       "word": w["word"]})

            for i in range(0, len(clip_words), 3):
                chunk = clip_words[i:i + 3]
                if not chunk:
                    continue
                c_start = chunk[0]["start"]
                c_end   = chunk[-1]["end"]
                if c_end - c_start < 0.3:
                    c_end = c_start + 0.3
                words_text = [w["word"] for w in chunk]
                chunks.append({
                    "text":   " ".join(words_text),
                    "start":  c_start,
                    "end":    c_end,
                    "has_kw": any(_is_keyword(w) for w in words_text),
                })
        else:
            # ── Segment-level fallback (no word timestamps) ────────────
            all_words = seg["text"].split()
            n_chunks  = max(1, (len(all_words) + 3) // 4)
            chunk_dur = (adj_end - adj_start) / n_chunks
            for idx in range(n_chunks):
                chunk = all_words[idx * 4:(idx + 1) * 4]
                if not chunk:
                    continue
                c_start = adj_start + idx * chunk_dur
                c_end   = c_start + chunk_dur
                chunks.append({
                    "text":   " ".join(chunk),
                    "start":  c_start,
                    "end":    c_end,
                    "has_kw": any(_is_keyword(w) for w in chunk),
                })

    return chunks


def _burn_subtitles_to_clip(
        chunks: list, clip_dur: float,
        main_clip: str, output_clip: str,
        res_w: int, res_h: int,
        font_size: int, margin_v: int,
        work_dir: str,
        brand_text: str = "",
        brand_position: str = "top-right") -> bool:
    """
    Burn subtitles into clip using Pillow strip PNGs + FFmpeg movie= filter.

    Key differences from the old webm approach:
    - Renders small *strip* PNGs (res_w × strip_h) instead of full-frame images
      → much less memory & disk I/O per frame
    - Uses FFmpeg movie= filter to load each PNG directly into filter_complex
      → no intermediate video file, no codec alpha issues, single FFmpeg pass
    - overlay filter with enable='between(t,...)' handles timing purely in FFmpeg

    No libass required. Supports bold text, black outline, keyword highlight (yellow).
    Returns True on success.
    """
    if not os.path.exists(main_clip) or os.path.getsize(main_clip) < 1000:
        print(f"    [ERROR] main_clip tidak ditemukan: {main_clip}")
        return False

    # ── Fast-path: nothing to burn ────────────────────────────────────────
    if not chunks and not brand_text:
        import shutil as _sh
        _sh.copy2(main_clip, output_clip)
        return True

    from PIL import Image, ImageDraw

    font    = _load_subtitle_font(font_size)
    outline = 3  # px black border

    # ── 1. Render each chunk as a small RGBA strip PNG ───────────────────
    # Strip is only as tall as needed (font height + outline + padding).
    # This is ~20-50× smaller than a full 1080×1920 frame → much faster.
    pad     = 14                                      # vertical padding
    strip_h = int(font_size * 1.8) + outline * 2 + pad
    strip_h = max(strip_h, 72)                        # minimum 72 px tall
    # Y-position of the strip's top edge in the full video frame
    overlay_y = res_h - strip_h - margin_v

    chunk_pngs = []   # list of (t_start, t_end, png_path)

    for i, c in enumerate(chunks):
        png_path = os.path.join(work_dir, f"sub_{i:04d}.png")
        img  = Image.new("RGBA", (res_w, strip_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        text = c["text"]
        fg   = (255, 255, 0, 255) if c["has_kw"] else (255, 255, 255, 255)

        # Measure rendered text size
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:                        # Pillow < 9.2
            tw, th = draw.textsize(text, font=font)

        x = max(outline, (res_w - tw) // 2)          # horizontally centered
        y = (strip_h - th) // 2                       # vertically centered in strip

        # Black outline (draw at every offset around the text)
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font,
                              fill=(0, 0, 0, 255))
        # Soft drop shadow for extra depth
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 180))
        # Main text
        draw.text((x, y), text, font=font, fill=fg)

        img.save(png_path, "PNG")
        chunk_pngs.append((c["start"], c["end"], png_path))

    # ── 2. Build FFmpeg filter_complex with movie= sources ───────────────
    # Each PNG is loaded with movie= (reads alpha natively — no codec).
    # Then chained overlay filters apply each strip at the right time window.
    #
    # filter_complex structure:
    #   movie='/a/b/sub_0000.png'[s0];
    #   movie='/a/b/sub_0001.png'[s1];
    #   ...
    #   [0:v][s0]overlay=0:<y>:enable='between(t,T0,T1)'[v0];
    #   [v0][s1]overlay=0:<y>:enable='between(t,T1,T2)'[v1];
    #   ...
    #   [vN-1]  ← final labelled output

    fc_parts = []

    if chunk_pngs:
        # Source declarations
        for i, (_, _, png_path) in enumerate(chunk_pngs):
            safe_path = png_path.replace("\\", "/").replace("'", "\\'")
            fc_parts.append(f"movie='{safe_path}'[s{i}]")

        # Overlay chain
        prev_lbl = "0:v"
        for i, (t_start, t_end, _) in enumerate(chunk_pngs):
            out_lbl = f"v{i}"
            fc_parts.append(
                f"[{prev_lbl}][s{i}]overlay=0:{overlay_y}"
                f":enable='between(t,{t_start:.3f},{t_end:.3f})'[{out_lbl}]"
            )
            prev_lbl = out_lbl
        final_lbl = prev_lbl
    else:
        # No subtitle chunks — only brand text will be applied
        final_lbl = "0:v"

    # Optional brand/watermark text drawn on top of everything
    if brand_text:
        safe_b = escape_ffmpeg_text(brand_text)
        pos_map = {
            "top-right":    "x=w-text_w-20:y=20",
            "top-left":     "x=20:y=20",
            "bottom-right": "x=w-text_w-20:y=h-text_h-20",
            "bottom-left":  "x=20:y=h-text_h-20",
        }
        pos = pos_map.get(brand_position, "x=w-text_w-20:y=20")
        brand_out = "vb"
        fc_parts.append(
            f"[{final_lbl}]drawtext=text='{safe_b}'"
            f":fontsize=24:fontcolor=white@0.7:{pos}[{brand_out}]"
        )
        final_lbl = brand_out

    fc_string = ";".join(fc_parts)

    # ── 3. Single FFmpeg pass: composite everything ───────────────────────
    if fc_string:
        cmd = [
            "ffmpeg", "-y",
            "-i", main_clip,
            "-filter_complex", fc_string,
            "-map", f"[{final_lbl}]",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            output_clip
        ]
    else:
        # Truly nothing to do (empty chunks, no brand text) — stream copy
        cmd = [
            "ffmpeg", "-y",
            "-i", main_clip,
            "-c", "copy",
            output_clip
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(output_clip) and os.path.getsize(output_clip) > 1000
    if not ok:
        print(f"    [WARNING] Subtitle burn failed:\n{r.stderr[-500:]}")
    return ok


def escape_ffmpeg_text(text: str) -> str:
    """Escape text untuk drawtext filter FFmpeg."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    # Limit panjang teks
    if len(text) > 80:
        text = text[:77] + "..."
    return text


def safe_remove(path: str):
    """Hapus file tanpa error."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
