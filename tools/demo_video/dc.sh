#!/usr/bin/env bash
# docker compose for the video project only (own project name, database, port and subnet).
cd "$(dirname "$0")/../.."
export PATH="$HOME/.orbstack/bin:$PATH"
exec docker compose -p vme-video -f docker-compose.yml -f tools/demo_video/compose.video.yml "$@"
