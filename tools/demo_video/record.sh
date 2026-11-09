#!/usr/bin/env bash
# Rebuild the demo video from scratch: fresh database, AI drafts, recording, MP4.
#   tools/demo_video/record.sh            # everything, about 15 minutes
#   SKIP_BUILD=1 tools/demo_video/record.sh   # reuse vme_video_fresh from an earlier build (about 9 minutes)
# The voice-over is generated first, with the engine of VOICE_ENGINE in tools/demo_video/.env
# (default: the macOS voice Ellen); see docs/dev/demo-video.md.
# Result: build/demo_video/quotis-demo.mp4 and quotis-promo.mp4 (outside git). See docs/dev/demo-video.md.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/build/demo_video"
DC="$HERE/dc.sh"

if [[ -z "${SKIP_BUILD:-}" ]]; then
    "$HERE/build_db.sh"
    # Keep a copy of the fresh database, so reset_db.sh can start every take from the same state.
    "$DC" stop odoo
    "$DC" exec -T db dropdb -U odoo --if-exists vme_video_fresh
    "$DC" exec -T db createdb -U odoo -T vme_video vme_video_fresh
fi
# Voice-over: VOICE_ENGINE in tools/demo_video/.env (say, the default; elevenlabs; connector; none).
ENGINE="$(grep -E '^VOICE_ENGINE=' "$HERE/.env" 2>/dev/null | cut -d= -f2 | tr -d ' "')"
case "${ENGINE:-say}" in
    say) python3 "$HERE/voice_say.py" ;;
    elevenlabs) python3 "$HERE/voice.py" ;;
    connector) python3 "$HERE/voice_connector.py" manifest ;;  # clips made beforehand via the connector
    none) rm -f "$OUT/voice/manifest.json" ;;
    *) echo "Onbekende VOICE_ENGINE: $ENGINE (say, elevenlabs, connector of none)" >&2; exit 1 ;;
esac
"$DC" build recorder
"$HERE/reset_db.sh"

rm -rf "$OUT/raw"
"$DC" run --rm -T recorder python3 tools/demo_video/record.py --out build/demo_video/raw
python3 "$HERE/make_video.py" "$OUT/raw" "$OUT/quotis-demo.mp4"
if [[ -f "$OUT/voice/manifest.json" ]]; then
    python3 "$HERE/promo.py" "$OUT/raw" "$OUT/quotis-promo.mp4"
fi
