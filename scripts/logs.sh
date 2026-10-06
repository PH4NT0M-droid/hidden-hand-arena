#!/usr/bin/env bash
# Read the arena + nginx logs without monitoring them live.
# Container logs rotate automatically (10 MB x3 per service, see docker-compose.yml).
#
# Usage:
#   ./scripts/logs.sh                  tail the last 200 lines of everything
#   ./scripts/logs.sh -f               follow live (the only "monitoring" you may ever need)
#   ./scripts/logs.sh arena            only the arena (app + access log)
#   ./scripts/logs.sh nginx            only nginx (proxy access + errors)
#   ./scripts/logs.sh --errors         5xx responses, tracebacks, failures
#   ./scripts/logs.sh --uploads        team registrations and bot uploads
#   ./scripts/logs.sh --export FILE    dump everything with timestamps to FILE
set -euo pipefail
cd "$(dirname "$0")/.."

FOLLOW=""
SERVICE=""
MODE="tail"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--follow) FOLLOW="-f"; shift ;;
    arena|nginx) SERVICE="$1"; shift ;;
    --errors) MODE="errors"; shift ;;
    --uploads) MODE="uploads"; shift ;;
    --export) MODE="export"; EXPORT_FILE="${2:?usage: logs.sh --export FILE}"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 1 ;;
  esac
done

case "$MODE" in
  tail)
    # shellcheck disable=SC2086
    exec docker compose logs --tail=200 $FOLLOW $SERVICE
    ;;
  errors)
    # 5xx from either access log, Python tracebacks, job failures.
    # shellcheck disable=SC2086
    docker compose logs --no-color --tail=2000 $SERVICE 2>&1 \
      | grep -iE '" [5][0-9]{2} [0-9]+|traceback|error|failed|  ! ' \
      | tail -100
    ;;
  uploads)
    # Registrations ("+ team X") and uploads ("upload TEAM: ...") come from arena.py.
    docker compose logs --no-color --tail=5000 arena 2>&1 \
      | grep -E '\+ team |upload ' \
      | tail -100
    ;;
  export)
    docker compose logs --no-color -t $SERVICE > "$EXPORT_FILE"
    echo "wrote $EXPORT_FILE"
    ;;
esac
