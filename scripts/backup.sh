#!/usr/bin/env bash
# Consistent backup of everything that matters: the SQLite DB, uploaded bots,
# and the hidden live/final seeds. Never copy arena.db off a live container
# (WAL files make that snapshot corrupt); VACUUM INTO takes a consistent copy.
# Usage: ./scripts/backup.sh   (writes backups/hh-<stamp>.tgz)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups

STAMP="$(date +%Y%m%d-%H%M%S)"
CID="$(docker compose ps -q arena)"
if [[ -z "$CID" ]]; then
  echo "error: arena container is not running (docker compose up -d first)" >&2
  exit 1
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "==> snapshotting database (VACUUM INTO, safe on a live arena)"
docker compose exec -T arena python3 -c \
  "import sqlite3; s=sqlite3.connect('/data/arena.db'); s.execute(\"VACUUM INTO '/tmp/arena-backup.db'\"); s.close()"
docker cp "$CID:/tmp/arena-backup.db" "$TMPDIR/arena.db"
docker compose exec -T arena rm -f /tmp/arena-backup.db >/dev/null

echo "==> copying uploads and hidden seeds"
docker cp "$CID:/data/subs" "$TMPDIR/subs"
for seed in live_seed final_seed; do
  docker cp "$CID:/data/$seed" "$TMPDIR/$seed" 2>/dev/null || true
done

tar -czf "backups/hh-$STAMP.tgz" -C "$TMPDIR" .
ls -la "backups/hh-$STAMP.tgz"
echo "backup complete: backups/hh-$STAMP.tgz"
echo "keep one copy off this machine before the final."
