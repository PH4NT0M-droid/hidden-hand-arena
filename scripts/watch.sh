#!/usr/bin/env bash
# Hands-off health log for the event. Add to cron on the server:
#
#   */5 * * * * /home/user/hiddenhand/scripts/watch.sh
#
# Every 5 minutes it appends one line to logs/health.log:
#   2026-10-08T18:05:01 ok 200 0.12s
#   2026-10-08T18:10:01 FAIL site HTTP 000 (curl exit 7)
# Success lines let you prove after the event that the site never went down;
# FAIL lines tell you exactly when to look in scripts/logs.sh --errors.
# It never restarts anything itself: `restart: unless-stopped` in
# docker-compose.yml already brings crashed containers back.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

STAMP="$(date +%Y-%m-%dT%H:%M:%S)"
LOG="logs/health.log"

PORT="$(docker compose port nginx 80 2>/dev/null | sed 's/.*://')"
if [[ -z "$PORT" ]]; then
  echo "$STAMP FAIL stack is down (no nginx port)" >> "$LOG"
  exit 0
fi

START="$(date +%s%N)"
CODE="$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "http://127.0.0.1:${PORT}/" 2>/dev/null || echo "000")"
END="$(date +%s%N)"
DT="$(awk -v s="$START" -v e="$END" 'BEGIN { printf "%.2fs", (e - s) / 1e9 }' 2>/dev/null || echo "?")"

if [[ "$CODE" == "200" ]]; then
  echo "$STAMP ok $CODE $DT" >> "$LOG"
else
  echo "$STAMP FAIL site HTTP $CODE" >> "$LOG"
fi
