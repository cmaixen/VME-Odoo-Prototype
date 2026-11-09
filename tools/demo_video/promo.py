"""Cut the short promo version (about a minute) out of the recording of record.py.

    python3 tools/demo_video/promo.py build/demo_video/raw build/demo_video/quotis-promo.mp4

Each shot starts where record.py logged a voice-over line (timeline.json) and lasts as long as that
line, so the caption in the picture is the sentence the viewer hears. The same voice and clips as
the long version; only the title and closing lines are separate (#promo_intro, #promo_outro).
No music: there is none whose licence we have documented.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from make_video import TRIM, VOICE_DIR, duration

LEAD = 0.4   # seconds of picture before the voice starts
TAIL = 0.5   # and after it ends
FADE = 0.25

# (segment, caption key): the strongest moments, in the order of the story.
SHOTS = [
    ("1_staff", "Vannacht mailde de eigenaar van A4 over een lek. De AI-assistent zette een antwoord klaar."),
    ("1_staff", "Het voorstel van de AI-assistent: nog niet verstuurd. Uw medewerker kijkt het na."),
    ("1_staff", "Verdeeld over 12 eigenaars: alleen de appartementen, want garages gebruiken de lift niet."),
    ("1_staff", "De AI las de drie offertes voor de gevel. De aandachtspunten staan in het geel."),
    ("1_staff", "De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is, tot op de "
                "cent en ook bij een verkoop midden in het jaar."),
    ("2_owner", "Jaarafrekening 2026, voorlopig: het saldo in zijn voordeel."),
    ("2_owner", "En onderaan zijn aandeel in de liftfactuur van Keuringsdienst Voorbeeld vzw: de mail van de "
                "leverancier van daarnet."),
    ("3_extra", "De lekmail van A4: Residentie Linde, kavels A4 en G4, en het voorstel van de AI-assistent, nog "
                "niet verstuurd."),
]


def cut(video, start, length, clip, offset, target):
    """One shot: `length` seconds of `video` from `start`, with `clip` starting `offset` seconds in."""
    delay = int(offset * 1000)
    audio = (f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={delay}:all=1,"
             f"apad,atrim=0:{length:.2f},afade=t=out:st={length - FADE:.2f}:d={FADE}[a]")
    picture = (f"[0:v]fps=25,scale=1920:1080,fade=t=in:st=0:d={FADE},"
               f"fade=t=out:st={length - FADE:.2f}:d={FADE},format=yuv420p[v]")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(video),
        "-i", str(clip), "-filter_complex", f"{picture};{audio}", "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", str(target),
    ], check=True)


def main(raw, target):
    raw, target = Path(raw), Path(target)
    manifest = json.loads((VOICE_DIR / "manifest.json").read_text())
    videos = {name: next((raw / name).glob("*.webm")) for name in ("1_staff", "2_owner", "3_extra")}
    timelines = {name: {item["key"]: item for item in json.loads((raw / name / "timeline.json").read_text())}
                 for name in videos}
    parts = []
    with tempfile.TemporaryDirectory() as tmp:
        def add(video, start, length, key, offset):
            part = Path(tmp) / f"{len(parts):02d}.mp4"
            cut(video, start, length, VOICE_DIR / manifest[key]["file"], offset, part)
            parts.append(part)

        # Title: the opening card of the long version, with the short opening line.
        intro = manifest["#promo_intro"]["duration"]
        add(videos["1_staff"], TRIM + 0.3, intro + 1.4, "#promo_intro", 0.7)
        for name, key in SHOTS:
            item = timelines[name].get(key)
            if not item:
                sys.exit(f"{name}: geen opname van {key[:60]!r}; neem opnieuw op met voice-over.")
            add(videos[name], item["t"] - LEAD, item["duration"] + LEAD + TAIL, key, LEAD)
        # Closing card: Quotis and "de software zet alles klaar, een mens beslist".
        outro_item = timelines["3_extra"]["#outro"]
        outro = manifest["#promo_outro"]["duration"]
        add(videos["3_extra"], outro_item["t"] - 0.4, outro + 2.0, "#promo_outro", 0.5)

        listing = Path(tmp) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-movflags", "+faststart", str(target)], check=True)
    print(f"{target}: {duration(target):.0f} seconden")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
