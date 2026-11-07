"""Join the WebM segments of record.py into one MP4 (H.264, 1920x1080, 25 fps).

The captions are already in the picture (overlay.js), so this only trims the blank first frames
of each segment, fades between them and encodes. Runs on the host with ffmpeg and ffprobe.

    python3 tools/demo_video/make_video.py build/demo_video/raw build/demo_video/quotis-demo.mp4
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SEGMENTS = ["1_staff", "2_owner", "3_extra"]
TRIM = 0.6  # seconds of white page before the first paint of a new browser context
FADE = 0.5


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


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
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-ss", str(TRIM), "-i", str(videos[0]),
                "-vf", f"fps=25,scale=1920:1080,{fades},format=yuv420p",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(part),
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
