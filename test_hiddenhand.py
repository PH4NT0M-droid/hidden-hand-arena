"""Run: python test_hiddenhand.py   (about a minute; spins up a throwaway arena)"""

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
    env = dict(os.environ, ARENA_DATA=str(tmp / "data"), PORT=str(p), COOLDOWN="0", DEALS="10", WORKERS="2")
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

        reg = lambda n: opener.open(base + "/register", urllib.parse.urlencode({"name": n}).encode()).read().decode()
        page = reg("Gamma")
        assert "Registered" in page, page
        assert "is taken" in reg("Gamma") and "cannot start with House" in reg("House · naive")
        keys.append(page.split("team key is ")[1].split()[0])  # Gamma registered itself; same login path as the rest
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
    finally:
        srv.kill()
        srv.wait()
    out = run("final")
    assert "Alpha" in out and "Beta" in out, out


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
