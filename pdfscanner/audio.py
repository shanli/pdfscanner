from __future__ import annotations
import os
import re
import sys
import subprocess
import tempfile
from pdfscanner.extractor import Topic


def _check_macos():
    if sys.platform != "darwin":
        raise RuntimeError("Audio generation requires macOS (say + afconvert)")


def build_script(topic: Topic, voice_en: str = "Samantha") -> str:
    """Build the say-compatible script for a topic."""
    lines = [f"Topic {topic.num}. {topic.name}. [[slnc 1000]]"]
    for s in topic.sentences:
        en = re.sub(r'[\u4e00-\u9fff].*', '', s).strip(" .•·")
        en = re.sub(r'\s+', ' ', en)
        if len(en) < 8:
            continue
        lines.append(f"{en}. [[slnc 800]]")
    return "\n".join(lines)


def _say_to_m4a(
    script: str,
    voice: str,
    out_path: str,
    workers: int = 8,
) -> str:
    """Write script to temp file, call say once, convert to M4A."""
    _check_macos()
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "script.txt")
        aiff_path   = os.path.join(tmpdir, "out.aiff")
        wav_path    = os.path.join(tmpdir, "out.wav")

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, "-f", script_path],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["afconvert", aiff_path, wav_path,
             "-f", "WAVE", "-d", "LEI16@22050", "-c", "1"],
            check=True, capture_output=True,
        )
        r = subprocess.run(
            ["afconvert", wav_path, out_path, "-f", "m4af", "-d", "aac "],
            capture_output=True,
        )
        if r.returncode != 0:
            import shutil
            wav_out = out_path.replace(".m4a", ".wav")
            shutil.copy(wav_path, wav_out)
            return wav_out
    return out_path


def generate(
    topics: list[Topic],
    output_dir: str,
    voice_en: str = "Samantha",
    workers: int = 8,
) -> list[str]:
    """
    Generate one M4A per topic. Returns list of output file paths.
    Skips topics with no sentences.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for t in topics:
        if not t.sentences:
            continue
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', t.name)
        if isinstance(t.num, int):
            out_path = os.path.join(output_dir, f"Topic_{t.num:02d}_{safe_name}.m4a")
        else:
            out_path = os.path.join(output_dir, f"Topic_{safe_name}.m4a")
        script = build_script(t, voice_en=voice_en)
        path = _say_to_m4a(script, voice=voice_en, out_path=out_path, workers=workers)
        results.append(path)
        size = os.path.getsize(path) // 1024
        print(f"  {os.path.basename(path)}  {size}KB")
    return results
