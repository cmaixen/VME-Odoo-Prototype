"""Voice-over through the ElevenLabs connector in Claude (the default route, no API key needed).

The connector generates the clips (creative_generate_speech, one flow, one take per line); this
script only lists the lines and, once the clips are downloaded, writes the manifest that record.py,
make_video.py and promo.py read, exactly like voice.py does.

    python3 tools/demo_video/voice_connector.py lines      # numbered lines to generate, as JSON
    python3 tools/demo_video/voice_connector.py manifest   # after saving them as voice/NN.mp3

See docs/dev/demo-video.md, "Voice-over".
"""
import json
import sys
from pathlib import Path

from narration import LINES
from voice import OUT, duration


def main(command):
    if command == "lines":
        print(json.dumps([{"nr": i, "key": key, "text": text} for i, (key, text) in enumerate(LINES)],
                         ensure_ascii=False, indent=1))
        return
    manifest, missing = {}, []
    for i, (key, text) in enumerate(LINES):
        clip = OUT / f"{i:02d}.mp3"
        if not clip.exists():
            missing.append(clip.name)
            continue
        manifest[key] = {"file": clip.name, "duration": round(duration(clip), 3), "text": text}
    if missing:
        sys.exit(f"Ontbrekende fragmenten in {OUT}: {', '.join(missing)}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"{len(manifest)} fragmenten, samen {sum(m['duration'] for m in manifest.values()) / 60:.1f} minuten")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("lines", "manifest"):
        sys.exit(__doc__)
    main(sys.argv[1])
