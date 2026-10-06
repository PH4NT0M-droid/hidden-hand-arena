#!/usr/bin/env bash
# Restore a backup taken by scripts/backup.sh (e.g. moving hosts mid-event).
# The arena is stopped before the database files are swapped: SQLite must
# have no writer while arena.db is replaced, and stale WAL/journal files from
# the old database must not survive next to the restored one.
# Run this when nobody is uploading. Usage: ./scripts/restore.sh backups/hh-<stamp>.tgz
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
  echo "usage: $0 backups/hh-<stamp>.tgz" >&2
  exit 1
fi
BACKUP="$1"
if [[ ! -f "$BACKUP" ]]; then
  echo "error: no such file: $BACKUP" >&2
  exit 1
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
tar -xzf "$BACKUP" -C "$TMPDIR"

if [[ ! -f "$TMPDIR/arena.db" || ! -d "$TMPDIR/subs" ]]; then
  echo "error: $BACKUP does not look like a backup.sh archive (need arena.db + subs/)" >&2
  exit 1
fi

# The container only needs to exist for `docker cp`; it must NOT be running
# for the file swap, but `docker exec` needs it running for the cleanup first.
CID="$(docker compose ps -aq arena)"
if [[ -z "$CID" ]]; then
  docker compose create arena >/dev/null
  CID="$(docker compose ps -aq arena)"
fi

echo "==> clearing live database files inside the running arena"
docker compose exec -T arena rm -f /data/arena.db-wal /data/arena.db-shm /data/arena.db-journal
docker compose exec -T arena rm -rf /data/subs

echo "==> stopping arena (no writer may hold the DB during restore)"
docker compose stop arena >/dev/null

echo "==> restoring database, uploads and seeds into volume hh-data"
docker cp "$TMPDIR/arena.db" "$CID:/data/arena.db"
docker cp "$TMPDIR/subs" "$CID:/data/subs"
for seed in live_seed final_seed; do
  if [[ -f "$TMPDIR/$seed" ]]; then
    docker cp "$TMPDIR/$seed" "$CID:/data/$seed"
  fi
done

echo "==> starting arena again"
docker compose start arena >/dev/null
docker compose ps
echo "verify: open the site and check the standings, then run"
echo "  docker compose exec arena python arena.py teams"
echo "if you moved hosts."
