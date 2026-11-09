"""Put the voice-over moments of timeline.json on the clock of the video itself.

record.py logs when each sentence starts by the wall clock, but Playwright's WebM does not run
exactly on that clock: in a five-minute take it drifts by several seconds. So at every sentence
overlay.js flips a small marker in the corner of the page, and we read the moments of those flips
from the video itself. The result is "v": seconds in the raw WebM. (Matching on the caption band
alone was not reliable: a new caption of the same size barely changes the picture.)
"""
import json
import subprocess

# The sync marker of overlay.js: a 12x12 square 8 px from the bottom-right corner, magenta for an
# even sentence and green for an odd one. We read the middle 6x6 pixels.
MARK = "crop=6:6:1903:1063"
FPS = 25


def mark_changes(video):
    """Times (s) at which the marker shows a new colour; frames without a marker are skipped."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={FPS},{MARK},format=rgb24",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    size = 6 * 6 * 3
    changes, state = [], None
    for i in range(len(raw) // size):
        px = raw[i * size:(i + 1) * size]
        r, g, b = (sum(px[c::3]) / 36 for c in range(3))
        colour = "m" if r > 170 and g < 100 and b > 170 else "g" if g > 170 and r < 100 and b < 100 else None
        if colour and colour != state:
            changes.append(round(i / FPS, 2))
            state = colour
    return changes


def align(video, timeline):
    """Add "v" (seconds in the raw video) to each entry of timeline, and return it: the n-th
    marker flip in the video is the n-th sentence."""
    changes = mark_changes(video)
    if len(changes) != len(timeline):
        raise SystemExit(f"{video}: {len(changes)} markeringen in beeld, {len(timeline)} zinnen in de tijdlijn.")
    for item, change in zip(timeline, changes):
        item["v"] = change
    return timeline


def load(raw, name, video):
    """timeline.json of a segment, aligned once and cached in timeline_aligned.json."""
    cached = raw / name / "timeline_aligned.json"
    if cached.exists():
        return json.loads(cached.read_text())
    source = raw / name / "timeline.json"
    timeline = align(video, json.loads(source.read_text())) if source.exists() else []
    cached.write_text(json.dumps(timeline, indent=1))
    return timeline
