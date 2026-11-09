"""Generate the voice-over clips of narration.py with the ElevenLabs text-to-speech API.

    python3 tools/demo_video/voice.py            # generates what is missing, about 6 minutes of speech
    python3 tools/demo_video/voice.py --voices   # lists the Dutch voices of the account

Reads ELEVENLABS_API_KEY (and optionally ELEVENLABS_VOICE_ID) from tools/demo_video/.env, which is in
.gitignore; the key never goes into code, git or the output of this script. The clips go to
build/demo_video/voice/ with a manifest.json (caption -> file and duration) that record.py and
make_video.py read. A clip is only generated again when its text, voice or model changes.

API: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id} (header xi-api-key) and
GET https://api.elevenlabs.io/v2/voices, see https://elevenlabs.io/docs/api-reference.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "build/demo_video/voice"
ENV_FILE = HERE / ".env"
API = "https://api.elevenlabs.io"
MODEL = "eleven_multilingual_v2"
# Calm and even: a bit more stability than the default, no exaggerated style.
VOICE_SETTINGS = {"stability": 0.6, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True, "speed": 0.97}

sys.path.insert(0, str(HERE))
from narration import LINES  # noqa: E402


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        sys.exit(f"ELEVENLABS_API_KEY ontbreekt. Vul de regel ELEVENLABS_API_KEY= in {ENV_FILE} in "
                 f"(kopie van {ENV_FILE.name}.example).")
    return key


def request(key, method, path, params=None, body=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        # The body explains the error (quota, unknown voice); it never contains the key.
        sys.exit(f"ElevenLabs {method} {path}: HTTP {error.code} {error.read()[:300].decode(errors='replace')}")


def dutch_voices(key):
    data = json.loads(request(key, "GET", "/v2/voices", {"language": "nl", "page_size": 100}))
    return data.get("voices", [])


def pick_voice(key):
    """ELEVENLABS_VOICE_ID if set; else a Dutch voice of the account, Flemish or Belgian first."""
    if os.environ.get("ELEVENLABS_VOICE_ID"):
        return os.environ["ELEVENLABS_VOICE_ID"], "ELEVENLABS_VOICE_ID uit .env"
    voices = dutch_voices(key)
    if not voices:
        sys.exit("Geen Nederlandstalige stem in het ElevenLabs-account. Voeg er een toe uit de Voice Library "
                 f"en zet haar id op de regel ELEVENLABS_VOICE_ID= in {ENV_FILE}.")

    def rank(voice):
        labels = " ".join(str(v) for v in (voice.get("labels") or {}).values()).lower()
        return (0 if ("flem" in labels or "belg" in labels or "vlaams" in labels) else 1, voice.get("name", ""))

    voice = sorted(voices, key=rank)[0]
    return voice["voice_id"], f"{voice.get('name')} {voice.get('labels') or ''}"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--voices", action="store_true", help="toon de Nederlandstalige stemmen en stop")
    args = parser.parse_args()
    key = load_env()
    if args.voices:
        for voice in dutch_voices(key):
            print(voice["voice_id"], voice.get("name"), voice.get("labels"))
        return

    voice_id, why = pick_voice(key)
    print(f"Stem: {why}; model {MODEL}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    texts = [text for _, text in LINES]
    for i, (caption, text) in enumerate(LINES):
        digest = hashlib.sha1(json.dumps([voice_id, MODEL, VOICE_SETTINGS, text]).encode()).hexdigest()[:16]
        clip = OUT / f"{digest}.mp3"
        if not clip.exists():
            body = {"text": text, "model_id": MODEL, "voice_settings": VOICE_SETTINGS, "seed": 7,
                    # Neighbouring lines keep the intonation of one continuous narration.
                    "previous_text": texts[i - 1] if i else None,
                    "next_text": texts[i + 1] if i + 1 < len(texts) else None}
            clip.write_bytes(request(key, "POST", f"/v1/text-to-speech/{voice_id}",
                                     {"output_format": "mp3_44100_128"}, body))
            print(f"+ {clip.name}  {text[:70]}", flush=True)
        manifest[caption] = {"file": clip.name, "duration": round(duration(clip), 3), "text": text}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    total = sum(item["duration"] for item in manifest.values())
    print(f"{len(manifest)} fragmenten, samen {total / 60:.1f} minuten: {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
