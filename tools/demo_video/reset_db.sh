#!/usr/bin/env bash
# Put vme_video back to the state right after build_db.sh (the copy vme_video_fresh), then run
# prepare.py: the AI drafts of "Vooraf". Takes about half a minute, so every take starts fresh.
set -euo pipefail
DC="$(dirname "$0")/dc.sh"
"$DC" stop odoo
"$DC" exec -T db dropdb -U odoo --if-exists vme_video
"$DC" exec -T db createdb -U odoo -T vme_video_fresh vme_video
"$DC" up -d odoo
until curl -fs -o /dev/null http://localhost:8695/web/login; do sleep 1; done
"$DC" run --rm -T recorder python3 tools/demo_video/prepare.py
