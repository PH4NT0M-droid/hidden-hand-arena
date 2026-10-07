"""Run: python test_hiddenhand.py   (about a minute; spins up a throwaway arena)"""

import gzip
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bot_loader import check_source, load_bot_class  # noqa: E402
from engine import play_deal, play_match  # noqa: E402

HEADER = "# Team Name: {}\n# Members: A (1), B (2), C (3)\n# Mentor: M\n"
SHARP = (HERE / "strategies/sharp.py").read_text().split("\n", 3)[3]
CHEAT = """
class Bot:
    def move(self, obs):
        return None
    def quote(self, obs):
        __import__("os").system("echo pwned")
        return 105
    def respond(self, obs, price):
        return 0
"""


def test_engine():
    naive, sharp = (load_bot_class(HERE / f"strategies/{n}.py") for n in ("naive", "sharp"))
    # Same bot in both seats of a mirrored match: exactly zero.
    assert play_match(sharp, sharp, n_deals=50)["pnl"] == [0.0, 0.0]
    # Keeping every deal's log must not change a single result.
    plain, logged = play_match(sharp, naive, n_deals=30, seed=4), play_match(sharp, naive, n_deals=30, seed=4, keep_logs=True)
    assert logged.pop("logs") and plain == logged and len(play_match(sharp, naive, 3, keep_logs=True)["logs"]) == 6
    # A deal is zero-sum apart from what was paid to the house.
    r = play_deal(sharp(), naive(), 5)
    assert abs(sum(r["pnl"]) + sum(r["log"]["spent"])) < 1e-6
    # Positions never pass the limit.
    assert all(abs(p) <= 10 for p in r["log"]["positions"])
    # The ladder holds: sharp beats naive.
    m = play_match(sharp, naive, n_deals=200)
    assert m["pnl"][0] > 0 and m["score"][0] > 0 > m["score"][1]
    assert play_match(sharp, sharp, n_deals=20)["score"] == [0.0, 0.0]
    from engine import score
    assert score([100.0, 0.0, -1.0, 0.0]) == (10 - 1) / 2   # sqrt scale, per mirrored pair


def test_sandbox(tmp: Path):
    from sandbox import SandboxedBot
    cheat = tmp / "cheat.py"
    cheat.write_text(HEADER.format("Cheat") + CHEAT)
    assert check_source(cheat).ok is False          # static gate catches __import__
    box = SandboxedBot(cheat, "cheat")              # and the sandbox refuses it at runtime
    naive = load_bot_class(HERE / "strategies/naive.py")
    r = play_match(box.new_deal, naive, n_deals=3)
    box.close()
    assert any("not allowed" in k for k in r["notes"][0]), r["notes"]


def test_arena(tmp: Path):
    port = socket.socket(); port.bind(("127.0.0.1", 0)); p = port.getsockname()[1]; port.close()
    env = dict(os.environ, ARENA_DATA=str(tmp / "data"), PORT=str(p), COOLDOWN="0", DEALS="10", WORKERS="2",
               ADMIN_KEY="test-admin-key")
    run = lambda *a: subprocess.run([sys.executable, str(HERE / "arena.py"), *a], env=env,
                                    capture_output=True, text=True, check=True).stdout
    keys = [run("add-team", n).split(": ")[1].strip() for n in ("Alpha", "Beta")]
    srv = subprocess.Popen([sys.executable, str(HERE / "arena.py")], env=env)
    base = f"http://127.0.0.1:{p}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base, timeout=1)
                break
            except OSError:
                time.sleep(0.2)

        def upload(key, name, body):
            opener.open(base + "/login", urllib.parse.urlencode({"key": key}).encode())
            b = "XbOuNdArY"
            data = (f"--{b}\r\nContent-Disposition: form-data; name=\"bot\"; filename=\"{name}\"\r\n"
                    f"Content-Type: text/x-python\r\n\r\n{body}\r\n--{b}--\r\n").encode()
            req = urllib.request.Request(base + "/submit", data,
                                         {"Content-Type": f"multipart/form-data; boundary={b}"})
            return opener.open(req).read().decode()

        reg = lambda n, k="MentorHHAB2CD": opener.open(
            base + "/register", urllib.parse.urlencode({"name": n, "key": k}).encode()).read().decode()
        assert "not right" in reg("Gamma"), "a key the organisers never issued must not register a team"
        subprocess.run([sys.executable, str(HERE / "arena.py"), "load-keys", "-"], env=env, check=True,
                       input="mentor,key\nMentor,MentorHHAB2CD\nMentor,MentorHHEF3GH\n", text=True)
        assert "is taken" in reg("Alpha") and "cannot start with House" in reg("House · naive")
        page = reg("Gamma", "mentorhhab2cd")  # keys ignore case
        assert "Registered Gamma" in page, page
        assert "already belongs to Gamma" in reg("Delta")
        keys.append("MentorHHAB2CD")  # Gamma claimed its mentor's key; same login path as the rest
        assert "Choose a .py file" not in upload(keys[2], "g.py", "x")  # its key logs in and reaches the upload check
        page = upload(keys[0], "alpha.py", HEADER.format("Alpha") + SHARP)
        assert "Passed the check" in page, page
        page = upload(keys[1], "beta.py", HEADER.format("Beta") + "import os\n" + SHARP)
        assert "illegal import" in page
        upload(keys[1], "beta.py", HEADER.format("Beta") + SHARP)
        # 2 teams + 3 house bots = 10 fights.
        for _ in range(240):
            home = urllib.request.urlopen(base).read().decode()
            if home.count("Watch") >= 10:
                break
            time.sleep(0.5)
        assert home.count("Watch") >= 10, "fights did not finish"
        assert "Alpha" in home and "Beta" in home
        team = urllib.request.urlopen(base + "/team/Alpha").read().decode()
        link = team.split('href="/match/')[1].split('"')[0]
        fight = urllib.request.urlopen(base + "/match/" + link).read().decode()
        assert "Settles at" in fight and "hands swapped" in fight
        assert urllib.request.urlopen(base + "/kit.zip").read()[:2] == b"PK"
        test_logs(base, keys, tmp / "data")
        test_admin(base, upload, keys)
    finally:
        srv.kill()
        srv.wait()
    out = run("final")
    assert "Alpha" in out and "Beta" in out, out


def test_logs(base: str, keys: list[str], data: Path):
    def login(key):
        o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        o.open(base + "/login", urllib.parse.urlencode({"key": key}).encode())
        return o
    alpha, beta, anon = login(keys[0]), login(keys[1]), urllib.request.build_opener()
    page = alpha.open(base + "/team/Alpha").read().decode()
    assert "Cards are numbered 0 to 51" in page
    log = page.split('href="/log/')[1].split('"')[0]
    rows = [json.loads(l) for l in gzip.decompress(alpha.open(base + "/log/" + log).read()).decode().splitlines()]
    assert len(rows) == 20 and "Alpha" in rows[0]["names"] and len(rows[0]["rounds"]) == 5  # 10 deals, both ways
    house = next(x for x in page.split('href="/log/')[1:] if "Beta" not in
                 alpha.open(base + "/match/" + x.split(".jsonl")[0]).read().decode().split("<h1>")[1].split("</h1>")[0])
    for who in (beta, anon):  # Beta was not in Alpha-vs-house, and nobody logged out gets any log
        try:
            who.open(base + "/log/" + house.split('"')[0])
            raise AssertionError("someone got a log of a fight they did not play")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    assert 'href="/log/' not in beta.open(base + "/team/Alpha").read().decode()  # not even a link on others' pages
    assert "Download every deal" in alpha.open(base + "/match/" + log.split(".jsonl")[0]).read().decode()
    # A fight from before logs existed shows "no log", not a dead link.
    os.remove(data / "logs" / log.replace("/", "-"))
    assert "no log" in alpha.open(base + "/team/Alpha").read().decode()


def test_admin(base: str, upload, keys: list[str]):
    get = lambda o, path: o.open(base + path).read().decode()
    post = lambda o, path, **f: o.open(base + path, urllib.parse.urlencode(f).encode()).read().decode()
    on_board = lambda name: f'href="/team/{urllib.parse.quote(name)}"' in get(urllib.request.build_opener(), "/")
    anon = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    # Nobody but an organiser gets in, sees code, or acts.
    assert "Admin key" in get(anon, "/admin")
    try:
        get(anon, "/admin/sub/1")
        raise AssertionError("code was shown without the admin key")
    except urllib.error.HTTPError as e:
        assert e.code == 404
    assert "not right" in post(anon, "/admin/login", key="guess")
    assert "Admin key" in post(anon, "/admin/action", do="dq", team="Beta") and on_board("Beta")

    admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    page = post(admin, "/admin/login", key="test-admin-key")
    assert "Mentor keys used" in page and "Alpha" in page and keys[0] in page, page
    sid = page.split('href="/admin/sub/')[1].split('"')[0]
    assert "class Bot" in get(admin, f"/admin/sub/{sid}")

    assert "is disqualified" in post(admin, "/admin/action", do="dq", team="Beta")
    assert not on_board("Beta") and on_board("Alpha")
    assert "disqualified" in upload(keys[1], "beta.py", HEADER.format("Beta") + SHARP)
    assert "reinstated" in post(admin, "/admin/action", do="reinstate", team="Beta") and on_board("Beta")

    assert "is now Alpha Prime" in post(admin, "/admin/action", do="rename", team="Alpha", name="Alpha Prime")
    assert "already taken" in post(admin, "/admin/action", do="rename", team="Beta", name="Alpha Prime")
    assert on_board("Alpha Prime")
    assert "Alpha Prime" in upload(keys[0], "a.py", "x")  # the old key still logs the renamed team in
    assert "can upload again" in post(admin, "/admin/action", do="cooldown", team="Beta")
    assert "already works" in post(admin, "/admin/action", do="recheck", sub=sid) and on_board("Beta")
    bad = get(admin, "/admin").split('href="/admin/sub/')[1].split('"')[0]  # Alpha Prime's rejected "x"
    assert f"File #{bad}:" in post(admin, "/admin/action", do="recheck", sub=bad) and on_board("Alpha Prime")


SLOW = """
class Bot:
    def move(self, obs):
        while True:
            pass
    def quote(self, obs):
        return 50
    def respond(self, obs, price):
        return 0
"""


def test_time_limit(tmp: Path):
    os.environ["ARENA_DATA"] = str(tmp / "slow")
    import arena
    arena.setup()
    f = tmp / "slow.py"
    f.write_text(HEADER.format("Slow") + SLOW)
    with arena.db() as con:
        con.execute("insert into teams(name, key) values('Slow', 'k')")
        sid = con.execute("insert into subs(team, created, file, status) values('Slow', 0, ?, 'queued')",
                          (str(f),)).lastrowid
        sub = con.execute("select * from subs where id = ?", (sid,)).fetchone()
    t0 = time.time()
    arena.smoke(sub)
    with arena.db() as con:
        msg = con.execute("select message from subs where id = ?", (sid,)).fetchone()[0]
    assert msg.startswith(arena.TIME_ERROR), msg
    assert time.time() - t0 < 60, "a bot stuck in a loop held up the arena"


def test_schedule(tmp: Path):
    """House bots first, then the closest-rated bot; everyone climbs together; every pair exactly once."""
    import arena

    def fresh(name, teams):
        arena.DATA, arena.DB = tmp / name, tmp / name / "arena.db"
        arena.setup()
        with arena.db() as con:
            for t in teams:
                con.execute("insert into teams(name, key) values(?, ?)", (t, t))
                con.execute("insert into subs(team, created, file, status) values(?, 0, 'x.py', 'ok')", (t,))
        return {r["team"]: r["id"] for r in arena.entries(arena.db())}

    rating: dict[int, float] = {}

    def play(a, b):
        sb = rating.get(b, 0.0) if a <= 3 else 0.0  # house bots are ids 1-3, always the older side
        with arena.db() as con:
            con.execute("insert into matches(stage, a, b, pnl_a, pnl_b, deals, notes, replay, created, score_a, score_b)"
                        " values('live', ?, ?, 0, 0, 2, '[]', '[]', 0, ?, ?)", (a, b, -sb, sb))

    def run_all():
        played = []
        while (job := arena.next_job()) is not None:
            a, b = job[1]["id"], job[2]["id"]
            arena.BUSY.discard(("live", a, b))
            play(a, b)
            played.append((job[1]["team"], job[2]["team"]))
        return played

    # Placement: New meets the house bots, then Strong (rated closest), then Weak.
    ids = fresh("sched1", ("Strong", "Weak", "New"))
    rating.update({ids["Strong"]: 5.0, ids["Weak"]: -5.0, ids["New"]: 4.0})
    for a, b in [(1, 2), (1, 3), (2, 3), (ids["Strong"], ids["Weak"])] + \
            [(h, ids[t]) for t in ("Strong", "Weak") for h in (1, 2, 3)]:
        play(a, b)
    order = run_all()
    assert [o[1] for o in order[:3]] == ["New"] * 3 and all(o[0].startswith("House") for o in order[:3]), order
    assert order[3:] == [("Strong", "New"), ("Weak", "New")], order

    # Balance: two fresh uploads take turns instead of one going first; every pair once.
    ids = fresh("sched2", ("One", "Two", "Three"))
    order = run_all()
    pairs = [frozenset(o) for o in order]
    assert len(pairs) == len(set(pairs)) == 15, order  # 6 entries: all 15 pairs, none twice
    count = dict.fromkeys({t for o in order for t in o}, 0)
    for a, b in order:  # nobody gets fight k+1 while some bot still has fewer than k
        assert min(count[a], count[b]) == min(count.values()), (a, b, count, order)
        count[a] += 1
        count[b] += 1


if __name__ == "__main__":
    test_engine()
    print("engine ok")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_sandbox(Path(d))
        print("sandbox ok")
        test_arena(Path(d))
        print("arena ok")
        test_time_limit(Path(d))
        print("time limit ok")
        test_schedule(Path(d))
        print("schedule ok")
