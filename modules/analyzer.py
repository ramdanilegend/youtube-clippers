"""
Module 3: AI Content Analyzer
Menggunakan LLM (GPT/Claude) untuk menganalisis transkripsi dan
menentukan momen-momen penting yang layak di-clip.

Mendukung --context parameter untuk mengarahkan fokus konten.
"""

import json
import os


def analyze_transcript(transcript: dict, video_meta: dict,
                       max_clips: int = 10,
                       clip_min_duration: int = 30,
                       clip_max_duration: int = 90,
                       provider: str = "openai",
                       api_key: str = "",
                       model: str = "gpt-4o-mini",
                       context: str = "") -> list:
    """
    Analisis transkripsi dan identifikasi momen-momen penting.

    Args:
        context: Konteks/arah konten. Misal: "fokus tips investasi",
                 "cari momen lucu", "highlight drama & konflik"

    Returns:
        list of clip dicts
    """
    print(f"[Analyzer] Menganalisis transkripsi dengan {provider}/{model}...")
    if context:
        print(f"    Context: {context}")

    segments_text = format_segments_for_prompt(transcript["segments"])

    # Build context instruction
    context_instruction = ""
    if context:
        context_instruction = f"""
KONTEKS/ARAHAN KHUSUS:
{context}
Prioritaskan momen-momen yang RELEVAN dengan konteks di atas.
Abaikan momen yang tidak berhubungan kecuali sangat viral.
"""

    prompt = f"""Kamu adalah seorang content strategist YouTube yang ahli dalam membuat clip viral.

TUGAS: Analisis transkripsi video berikut dan identifikasi {max_clips} momen paling menarik yang bisa dijadikan clip pendek.

VIDEO INFO:
- Judul: {video_meta.get('title', 'Unknown')}
- Channel: {video_meta.get('channel', 'Unknown')}
- Bahasa: {transcript.get('language', 'auto')}
{context_instruction}
TRANSKRIPSI (dengan timestamp):
{segments_text}

ATURAN CLIP:
1. Setiap clip harus berdurasi antara {clip_min_duration}-{clip_max_duration} detik
2. Pilih momen yang: mengandung insight penting, kontroversial/mengejutkan, emosional, lucu, atau edukatif
3. Pastikan clip dimulai dan diakhiri di titik yang natural (tidak terpotong di tengah kalimat)
4. Setiap clip harus bisa berdiri sendiri tanpa konteks video penuh

UNTUK SETIAP CLIP, BERIKAN:
- clip_number: nomor urut (1, 2, 3, ...)
- title: judul pendek catchy (Bahasa Indonesia jika video berbahasa Indonesia)
- start_time: waktu mulai (detik, contoh: 125.5)
- end_time: waktu selesai (detik)
- key_point: poin utama clip (1 kalimat)
- hook: kalimat pembuka 3 detik yang bikin orang stay (bukan spoiler)
- commentary_intro: 1-2 kalimat konteks sebelum clip (engaging, tambah nilai baru)
- commentary_outro: 1 kalimat takeaway setelah clip
- tags: 3 hashtag relevan
- viral_score: skor 1-10

Urutkan dari viral_score tertinggi ke terendah.
FORMAT OUTPUT: JSON array saja, tanpa markdown.
[
  {{"clip_number": 1, "title": "...", "start_time": ..., "end_time": ..., "key_point": "...", "hook": "...", "commentary_intro": "...", "commentary_outro": "...", "tags": ["..."], "viral_score": 10}},
  ...
]"""

    # Call LLM
    response_text = call_llm(prompt, provider, api_key, model)

    # Parse JSON dari response
    clips = parse_llm_response(response_text)

    # Validasi dan sort
    valid_clips = []
    for clip in clips:
        try:
            clip["start_time"] = float(clip.get("start_time", 0))
            clip["end_time"] = float(clip.get("end_time", 0))
            clip["viral_score"] = int(clip.get("viral_score", 5))
            clip["clip_number"] = int(clip.get("clip_number", 0))
        except (ValueError, TypeError):
            continue
        duration = clip["end_time"] - clip["start_time"]
        if clip_min_duration <= duration <= clip_max_duration + 15:
            valid_clips.append(clip)

    valid_clips.sort(key=lambda x: x.get("viral_score", 0), reverse=True)
    valid_clips = valid_clips[:max_clips]

    print(f"    Ditemukan {len(valid_clips)} clip potensial")
    for c in valid_clips:
        duration = c["end_time"] - c["start_time"]
        print(f"    #{c['clip_number']} [{c['viral_score']}/10] "
              f"{duration:.0f}s - {c['title']}")

    return valid_clips


def analyze_multi_transcripts(transcripts: list, videos_meta: list,
                              max_clips: int = 10,
                              clip_min_duration: int = 30,
                              clip_max_duration: int = 90,
                              provider: str = "openai",
                              api_key: str = "",
                              model: str = "gpt-4o-mini",
                              context: str = "") -> list:
    """
    Analisis MULTIPLE transkripsi dan cari momen terbaik dari semua video.
    Return clips dengan tambahan field 'source_index' untuk tracking video asal.
    """
    print(f"[Analyzer] Menganalisis {len(transcripts)} video sekaligus...")
    if context:
        print(f"    Context: {context}")

    # Gabung semua transkripsi dengan label video
    combined_text = ""
    for i, (transcript, meta) in enumerate(zip(transcripts, videos_meta)):
        source_idx = meta.get("source_index", i + 1)
        combined_text += f"\n\n=== VIDEO {source_idx}: {meta.get('title', 'Unknown')} (Channel: {meta.get('channel', 'Unknown')}) ===\n"
        combined_text += format_segments_for_prompt(transcript["segments"])

    context_instruction = ""
    if context:
        context_instruction = f"""
KONTEKS/ARAHAN KHUSUS:
{context}
Prioritaskan momen-momen yang RELEVAN dengan konteks di atas.
Kombinasikan insight dari berbagai video untuk membuat clip yang lebih kaya.
"""

    prompt = f"""Kamu adalah seorang content strategist YouTube yang ahli dalam membuat clip viral.

TUGAS: Analisis transkripsi dari {len(transcripts)} video berikut dan identifikasi {max_clips} momen paling menarik yang bisa dijadikan clip pendek.
Clip boleh dari video manapun. Pilih yang TERBAIK dari semua video.

VIDEO INFO:
{chr(10).join(f"- Video {m.get('source_index', i+1)}: {m.get('title', '?')} ({m.get('channel', '?')})" for i, m in enumerate(videos_meta))}
{context_instruction}
TRANSKRIPSI (dengan timestamp per video):
{combined_text}

ATURAN CLIP:
1. Setiap clip harus berdurasi antara {clip_min_duration}-{clip_max_duration} detik
2. Pilih momen yang: mengandung insight penting, kontroversial/mengejutkan, emosional, lucu, atau edukatif
3. Pastikan clip dimulai dan diakhiri di titik yang natural
4. Setiap clip harus bisa berdiri sendiri
5. SERTAKAN field "source_video" berisi nomor video asal (1, 2, 3, ...)

UNTUK SETIAP CLIP, BERIKAN:
- clip_number, source_video (nomor video asal), title (catchy, Bahasa Indonesia jika video berbahasa Indonesia)
- start_time, end_time (detik)
- key_point (1 kalimat)
- hook (kalimat pembuka 3 detik, bukan spoiler)
- commentary_intro (1-2 kalimat konteks sebelum clip, tambah nilai baru)
- commentary_outro (1 kalimat takeaway)
- tags (3 hashtag)
- viral_score (1-10)

Urutkan dari viral_score tertinggi ke terendah.
FORMAT OUTPUT: JSON array saja, tanpa markdown.
[
  {{"clip_number": 1, "source_video": 1, "title": "...", "start_time": ..., "end_time": ..., "key_point": "...", "hook": "...", "commentary_intro": "...", "commentary_outro": "...", "tags": ["..."], "viral_score": 10}},
  ...
]"""

    response_text = call_llm(prompt, provider, api_key, model)
    clips = parse_llm_response(response_text)
    print(f"    [DEBUG] LLM returned {len(clips)} clips sebelum validasi durasi")

    valid_clips = []
    for clip in clips:
        # Pastikan start_time / end_time adalah float (LLM kadang return string)
        try:
            clip["start_time"] = float(clip.get("start_time", 0))
            clip["end_time"] = float(clip.get("end_time", 0))
            clip["viral_score"] = int(clip.get("viral_score", 5))
            clip["clip_number"] = int(clip.get("clip_number", 0))
        except (ValueError, TypeError):
            continue
        duration = clip["end_time"] - clip["start_time"]
        if not (clip_min_duration <= duration <= clip_max_duration + 15):
            print(f"    [DEBUG] Clip '{clip.get('title','?')}' dibuang: durasi {duration:.0f}s (min={clip_min_duration}, max={clip_max_duration+15})")
        else:
            valid_clips.append(clip)

    valid_clips.sort(key=lambda x: x.get("viral_score", 0), reverse=True)
    valid_clips = valid_clips[:max_clips]

    print(f"    Ditemukan {len(valid_clips)} clip potensial dari {len(transcripts)} video")
    for c in valid_clips:
        duration = c["end_time"] - c["start_time"]
        src = c.get("source_video", "?")
        print(f"    #{c['clip_number']} [V{src}] [{c['viral_score']}/10] "
              f"{duration:.0f}s - {c['title']}")

    return valid_clips


def format_segments_for_prompt(segments: list, window_sec: float = 20.0) -> str:
    """
    Format segments untuk prompt LLM, dikompresi ke time-window agar hemat token.

    Strategi:
    - Gabung segmen-segmen berurutan ke dalam bucket ~window_sec detik
    - Setiap bucket jadi 1 baris: [MM:SS] <gabungan teks>
    - Untuk video 48 menit (1681 segmen) → ~147 baris (vs 1681 baris lama)
    - Hemat ~65-70% input token tanpa kehilangan informasi konten
    """
    if not segments:
        return ""

    lines = []
    bucket_start = segments[0]["start"]
    bucket_texts: list = []

    for seg in segments:
        # Mulai bucket baru kalau sudah melewati window
        if seg["start"] - bucket_start >= window_sec and bucket_texts:
            lines.append(f"[{format_time(bucket_start)}] {' '.join(bucket_texts)}")
            bucket_start = seg["start"]
            bucket_texts = []

        text = seg.get("text", "").strip()
        if text:
            bucket_texts.append(text)

    # Flush sisa bucket terakhir
    if bucket_texts:
        lines.append(f"[{format_time(bucket_start)}] {' '.join(bucket_texts)}")

    return "\n".join(lines)


def format_time(seconds: float) -> str:
    """Convert detik ke format MM:SS."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def call_llm(prompt: str, provider: str, api_key: str, model: str) -> str:
    """Call LLM API dan return response text."""

    # Truncate prompt jika terlalu panjang.
    # Dengan kompresi window-20s, video 2 jam pun masuk di bawah 30k chars.
    MAX_PROMPT_CHARS = 32000
    est_tokens = len(prompt) // 4
    print(f"    [INFO] Prompt size: {len(prompt):,} chars (~{est_tokens:,} tokens)")
    if len(prompt) > MAX_PROMPT_CHARS:
        # Potong di batas baris agar tidak putus di tengah kalimat
        cut_pos = prompt.rfind("\n", 0, MAX_PROMPT_CHARS)
        if cut_pos < MAX_PROMPT_CHARS * 0.8:
            cut_pos = MAX_PROMPT_CHARS
        print(f"    [INFO] Dipotong ke {cut_pos:,} chars")
        prompt = prompt[:cut_pos] + "\n\n[TRANSCRIPT DIPOTONG]\n\n" + \
                 prompt[prompt.rfind("\nATURAN CLIP"):]   # Tetap sertakan aturan & format output

    try:
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Kamu adalah content strategist YouTube. Selalu output JSON valid."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096,
                response_format={"type": "json_object"} if "gpt-4" in model else None
            )
            return response.choices[0].message.content

        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system="Kamu adalah content strategist YouTube. WAJIB output JSON array valid saja, tanpa teks, tanpa markdown, tanpa penjelasan apapun sebelum atau sesudah JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        else:
            raise ValueError(f"Provider '{provider}' tidak didukung. Gunakan 'openai' atau 'anthropic'.")

    except Exception as e:
        print(f"    [ERROR] LLM call gagal: {e}")
        raise


def parse_llm_response(text: str) -> list:
    """Parse JSON dari LLM response (handle markdown code blocks dll)."""
    import re

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "clips" in data:
            return data["clips"]
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        pass

    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    print("    [WARNING] Gagal parse LLM response sebagai JSON")
    print(f"    [DEBUG] Raw response (100 chars): {text[:100]!r}")
    return []
