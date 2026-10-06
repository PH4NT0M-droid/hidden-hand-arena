#!/usr/bin/env bash
# Deploy (or redeploy) the Hidden Hand arena + nginx stack on a Linux server.
# Safe to re-run: rebuilds the image, keeps the hh-data volume, waits healthy.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null; then
  echo "error: docker is not installed (need Docker 20.10+ with 'compose' plugin)" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "created .env from .env.example -- set DEADLINE before the event."
fi

echo "==> building arena image"
docker compose build arena

echo "==> starting stack (data preserved in volume 'hh-data')"
docker compose up -d

# The host port nginx published (honours NGINX_HTTP_PORT from .env).
PORT="$(docker compose port nginx 80 | sed 's/.*://')"
echo "==> waiting for the arena to answer through nginx (port ${PORT}, up to 60s)"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "http://127.0.0.1:${PORT}/" | grep -q "HIDDEN"; then
  echo "error: arena is not answering on port ${PORT}; showing logs:" >&2
  docker compose logs --tail=50
  exit 1
fi

# The kit the participants download must be servable.
curl -fsS "http://127.0.0.1:${PORT}/kit.zip" -o /tmp/hh-kit-check.zip
if ! python3 -c "import zipfile,sys; zipfile.ZipFile('/tmp/hh-kit-check.zip').testzip()" 2>/dev/null; then
  echo "error: /kit.zip did not return a valid zip" >&2
  exit 1
fi
rm -f /tmp/hh-kit-check.zip

echo "==> status"
docker compose ps
echo
echo "arena is live at http://<server-ip>:${PORT}"
echo "next steps:"
echo "  teams:  docker compose exec arena python arena.py add-team \"Team Name\""
echo "  logs:   docker compose logs -f arena"
echo "  backup: ./scripts/backup.sh   (run on a cron during the event)"
