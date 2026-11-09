#!/usr/bin/env bash
# Build a fresh demo database for the video: vme_video on compose project vme-video, port 8695.
# Follows "Vooraf" in docs/demo.md, step 1. The demo server on 8069 (vme_demo) is not touched.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$HOME/.orbstack/bin:$PATH"
DC=(docker compose -p vme-video -f docker-compose.yml -f tools/demo_video/compose.video.yml)
DB=vme_video

"${DC[@]}" up -d db
sleep 3
"${DC[@]}" stop odoo || true
"${DC[@]}" exec -T db dropdb -U odoo --if-exists "$DB"
"${DC[@]}" run --rm odoo odoo -d "$DB" -i vme_belgie,vme_rentmeester,vme_website,vme_mail_plugin \
    --load-language=nl_BE --stop-after-init
echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_data(); env.cr.commit()" \
    | "${DC[@]}" run --rm -T odoo odoo shell -d "$DB" --no-http
echo "env = env(user=env.ref('base.user_admin')); env['vme.association']._load_demo_history(); env.cr.commit()" \
    | "${DC[@]}" run --rm -T odoo odoo shell -d "$DB" --no-http
"${DC[@]}" up -d odoo
echo "Odoo for the video: http://localhost:8695 (database $DB)"
