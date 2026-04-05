"""
Module 4: Text-to-Speech Engine
Menggunakan edge-tts (gratis, kualitas tinggi) untuk generate voiceover.
"""

import os
import asyncio
import subprocess


def generate_voiceover(text: str, output_path: str,
                       voice: str = "id-ID-ArdiNeural",
                       rate: str = "+0%") -> str:
    """
    Generate voiceover dari teks menggunakan edge-tts.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    async def _generate():
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

    # Run async function
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _generate()).result()
        else:
            loop.run_until_complete(_generate())
    except RuntimeError:
        asyncio.run(_generate())

    return output_path


def generate_clip_voiceovers(clip_data: dict, output_dir: str,
                              voice: str = "id-ID-ArdiNeural",
                              rate: str = "+0%",
                              outro_cta_text: str = "") -> dict:
    """
    Generate intro dan outro voiceover untuk satu clip.
    Juga generate CTA outro jika ada.

    Returns:
        dict: {
            "intro_audio": str (path),
            "outro_audio": str (path),
            "cta_audio": str (path),     # CTA subscribe dll
            "intro_duration": float,
            "outro_duration": float,
            "cta_duration": float,
            "hook_text": str,
            "intro_text": str,
            "outro_text": str,
        }
    """
    clip_num = clip_data["clip_number"]
    vo_dir = os.path.join(output_dir, f"clip_{clip_num:02d}_voiceover")
    os.makedirs(vo_dir, exist_ok=True)

    result = {}

    # Generate intro voiceover
    intro_text = clip_data.get("commentary_intro", "")
    if intro_text:
        intro_path = os.path.join(vo_dir, "intro.mp3")
        print(f"    Generating intro voiceover untuk clip #{clip_num}...")
        generate_voiceover(intro_text, intro_path, voice, rate)
        result["intro_audio"] = intro_path
        result["intro_duration"] = get_audio_duration(intro_path)
        result["intro_text"] = intro_text

    # Generate outro voiceover (commentary)
    outro_text = clip_data.get("commentary_outro", "")
    if outro_text:
        outro_path = os.path.join(vo_dir, "outro.mp3")
        print(f"    Generating outro voiceover untuk clip #{clip_num}...")
        generate_voiceover(outro_text, outro_path, voice, rate)
        result["outro_audio"] = outro_path
        result["outro_duration"] = get_audio_duration(outro_path)
        result["outro_text"] = outro_text

    # Generate CTA voiceover (subscribe etc)
    if outro_cta_text:
        cta_path = os.path.join(vo_dir, "cta.mp3")
        print(f"    Generating CTA voiceover untuk clip #{clip_num}...")
        generate_voiceover(outro_cta_text, cta_path, voice, rate)
        result["cta_audio"] = cta_path
        result["cta_duration"] = get_audio_duration(cta_path)

    # Hook text (teks overlay, bukan voiceover)
    result["hook_text"] = clip_data.get("hook", "")

    return result


def get_audio_duration(audio_path: str) -> float:
    """Dapatkan durasi file audio dalam detik."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
