# Running the Hidden Hand arena (no AWS needed)

The arena is one Python file (`arena.py`, standard library only) plus a SQLite database in
`ARENA_DATA`. Anything that can keep a Python process running for four days and give it a
public URL will do. Pick one option below.

## Before the event (any option)

```bash
# Teams register themselves on the Submit page. add-team is only for making one by hand:
python arena.py add-team "Team Name"     # prints the key
python arena.py teams                    # list every team and its key
```

Settings, all optional, set as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `DEADLINE` | none | e.g. `2026-10-08T18:00` (server's local time). Uploads close after it |
| `DEALS` | 200 | deals each way in a live fight |
| `FINAL_DEALS` | 500 | deals each way in a final fight |
| `COOLDOWN` | 600 | seconds between uploads per team |
| `WORKERS` | 2 | fights run at once. Set it to the number of CPU cores minus one |
| `ARENA_DATA` | `./arena_data` | database, uploaded files, hidden seeds. **Back this folder up** |
| `PORT` | 8000 | |

## Option A: a club laptop and a Cloudflare tunnel (free, about 5 minutes)

```bash
winget install Cloudflare.cloudflared    # once
python arena.py --tunnel
```

It prints a `https://….trycloudflare.com` link that works on any network. Post it on the group.

* The laptop must stay on, plugged in and online until the results are out. Turn off sleep
  (Settings › System › Power › Never).
* The link changes every time you restart. For a fixed link, make a free Cloudflare account
  and set up a *named* tunnel (`cloudflared tunnel login`, then `cloudflared tunnel create
  hiddenhand`). That needs a domain on Cloudflare.
* Allow Python through Windows Firewall if it asks.

## Option A2: any Linux server, no Docker (about 10 minutes)

Needs Python 3.10 or newer (`python3 --version`) and nothing else: no pip installs.

```bash
# 1. copy the hiddenhand folder over (from your laptop)
scp -r hiddenhand user@server:~/
#    moving from the laptop mid-event? copy arena_data too: same team keys, uploads, results
scp -r hiddenhand/arena_data user@server:~/hiddenhand/

# 2. on the server: prove it works there (about a minute; must end with "arena ok")
cd ~/hiddenhand && python3 test_hiddenhand.py

# 3. teams: one name per line in teams.txt, keys land in keys.txt (skip if you copied arena_data)
while read -r t; do python3 arena.py add-team "$t"; done < teams.txt > keys.txt

# 4. start it in a tmux session so it survives you logging out
tmux new -s arena
DEADLINE=2026-10-08T18:00 WORKERS=3 PORT=8000 python3 arena.py
#    detach with Ctrl-b then d; come back with: tmux attach -t arena
```

Open port 8000 in the server's firewall and share `http://<server-ip>:8000`, or for an https
link with no firewall change run `cloudflared tunnel --url http://localhost:8000` in a second
tmux window. The final on Thursday: `python3 arena.py final` in that folder.

## Option B: a free Linux VM (Oracle Cloud Always Free, or a college server)

Oracle's Always Free tier includes an ARM VM with 4 cores and 24 GB, which is plenty.
Inside the VM:

```bash
sudo apt install -y docker.io git
git clone [TBD: repo] && cd hiddenhand
sudo docker build -t hiddenhand .
sudo docker run -d --name arena --restart unless-stopped -p 80:8000 \
    -v hh-data:/data -e DEADLINE=2026-10-08T18:00 -e WORKERS=3 hiddenhand
sudo docker exec arena python arena.py add-team "Team Name"
```

Open port 80 in the VM's firewall (on Oracle: the subnet's security list, then
`sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT`). Share `http://<vm-ip>`. For https,
put Option A's `cloudflared tunnel --url http://localhost:80` in front of it.

Docker matters here. Submissions are untrusted code, and the container keeps them away from
the rest of the machine. Bots already run in locked-down worker processes with no file or
network access, and the container adds one more wall.

## Option C: Railway or Fly.io (a few dollars, no server to look after)

Both deploy straight from the `Dockerfile`. You **must attach a volume mounted at `/data`**,
or the database is lost on every redeploy.

* **Railway:** New Project › Deploy from GitHub repo › add a Volume at `/data` › set the
  variables › Generate Domain. Add teams from the service's shell:
  `python arena.py add-team "Name"`.
* **Fly.io:** `fly launch` (keep the Dockerfile), then `fly volumes create data --size 1`,
  add `[mounts] source="data" destination="/data"` to `fly.toml`, `fly deploy`.
  Teams: `fly ssh console -C 'python arena.py add-team "Name"'`.

Do not use Render's free tier. It sleeps when idle and wipes the disk.

## On the last day

1. At `DEADLINE` uploads close by themselves.
2. Run the final where the arena runs: `python arena.py final` (Docker:
   `sudo docker exec arena python arena.py final`). It plays every current entry against
   every other on a separate hidden seed and prints the standings. The site shows them at
   the top straight away.
3. Copy the `ARENA_DATA` folder somewhere safe. It holds every file and every result.

Count the time the final needs: with 30 entries there are about 500 fights, and 500 deals
each way takes about 5 to 10 s per fight per worker. With 3 workers, plan on 15 to 30 minutes.

## Logging (no monitoring needed)

Nobody has to watch a terminal during the event. Every request is logged by the
arena (with the real client address even behind nginx), every registration and
upload is logged with the team name, and nginx logs all proxy traffic. Container
logs rotate automatically (10 MB × 3 per service).

```bash
./scripts/logs.sh              # last 200 lines of everything
./scripts/logs.sh --errors     # 5xx responses, tracebacks, failed jobs
./scripts/logs.sh --uploads    # who registered / uploaded, and the verdict
./scripts/logs.sh --export day1.log   # dump everything for later
```

For a hands-off uptime record, log a heartbeat to `logs/health.log` every 5
minutes from cron:

```cron
*/5 * * * * /home/user/hiddenhand/scripts/watch.sh
```

After the event, `logs/health.log` shows the site never went down (or exactly
when it did), and `./scripts/logs.sh --export` preserves the full story.
Crashed containers restart by themselves (`restart: unless-stopped`).
