"""Voice-over with a voice of macOS itself (`say`): free, offline, the same voice for every line.

    python3 tools/demo_video/voice_say.py     # all lines of narration.py, about half a minute

Voice and rate come from tools/demo_video/.env (SAY_VOICE, SAY_RATE); the default is Ellen, the
Flemish (nl_BE) voice of macOS, at 175 words per minute. Writes build/demo_video/voice/manifest.json
like voice.py, so record.py, make_video.py and promo.py work the same with either engine.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from narration import LINES
from voice import ENV_FILE, OUT, duration


def settings():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    return os.environ.get("SAY_VOICE") or "Ellen", int(os.environ.get("SAY_RATE") or 175)


def main():
    voice, rate = settings()
    installed = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True).stdout
    if not any(line.split()[0] == voice for line in installed.splitlines() if line.strip()):
        sys.exit(f"Stem {voice!r} niet geïnstalleerd (Systeeminstellingen > Toegankelijkheid > Gesproken inhoud).")
    print(f"Stem: {voice} (macOS), {rate} woorden per minuut", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key, text in LINES:
            digest = hashlib.sha1(json.dumps([voice, rate, text]).encode()).hexdigest()[:16]
            clip = OUT / f"say_{digest}.mp3"
            if not clip.exists():
                aiff = Path(tmp) / "line.aiff"
                subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text], check=True)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "44100",
                                "-c:a", "libmp3lame", "-b:a", "128k", str(clip)], check=True)
            manifest[key] = {"file": clip.name, "duration": round(duration(clip), 3), "text": text}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"{len(manifest)} fragmenten, samen {sum(m['duration'] for m in manifest.values()) / 60:.1f} minuten")


if __name__ == "__main__":
    main()
