"""Join the WebM segments of record.py into one MP4 (H.264, 1920x1080, 25 fps).

The captions are already in the picture (overlay.js), so this trims the blank first frames of each
segment, fades between them, lays the voice-over clips (voice.py) on the times record.py logged in
timeline.json, and encodes. Runs on the host with ffmpeg and ffprobe.

    python3 tools/demo_video/make_video.py build/demo_video/raw build/demo_video/quotis-demo.mp4
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import align

SEGMENTS = ["1_staff", "2_owner", "3_extra"]
VOICE_DIR = Path(__file__).resolve().parents[2] / "build/demo_video/voice"
TRIM = 0.6  # seconds of white page before the first paint of a new browser context
FADE = 0.5
HIDE_MARK = "delogo=x=1895:y=1055:w=22:h=22"  # paints out the sync marker of overlay.js


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def voice_mix(timeline, length):
    """ffmpeg inputs and filter for the audio of one segment: each clip delayed to its moment
    in the video ("v" from align.py), and never on top of the previous one."""
    inputs, chains, labels = [], [], []
    free = 0.0
    for i, item in enumerate(timeline, start=1):
        inputs += ["-i", str(VOICE_DIR / item["file"])]
        start = max(item["v"] - TRIM, free)
        free = start + item["duration"] + 0.15
        delay = max(0, int(start * 1000))
        chains.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={delay}:all=1[c{i}]")
        labels.append(f"[c{i}]")
    # A silent bed of the full length, so every segment has the same audio format for the concat.
    chains.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{length:.2f}[bed]")
    mix = f"[bed]{''.join(labels)}amix=inputs={len(labels) + 1}:normalize=0:duration=first"
    chains.append(f"{mix},alimiter=limit=0.95[a]")
    return inputs, ";".join(chains)


def main(raw, target):
    raw, target = Path(raw), Path(target)
    parts = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in SEGMENTS:
            videos = sorted((raw / name).glob("*.webm"))
            if not videos:
                continue
            if len(videos) > 1:
                sys.exit(f"{name}: meer dan één video ({len(videos)}); maak de map leeg en neem opnieuw op.")
            length = duration(videos[0]) - TRIM
            part = Path(tmp) / f"{name}.mp4"
            fades = f"fade=t=in:st=0:d={FADE},fade=t=out:st={length - FADE:.2f}:d={FADE}"
            timeline = align.load(raw, name, videos[0])
            inputs, audio = voice_mix(timeline, length)
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-ss", str(TRIM), "-i", str(videos[0]), *inputs,
                "-filter_complex", f"[0:v]fps=25,scale=1920:1080,{HIDE_MARK},{fades},format=yuv420p[v];{audio}",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-t", f"{length:.2f}", str(part),
            ], check=True)
            parts.append(part)
            print(f"{name}: {length:.0f} s", flush=True)
        listing = Path(tmp) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-movflags", "+faststart", str(target)], check=True)
    print(f"{target}: {duration(target) / 60:.1f} minuten")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
