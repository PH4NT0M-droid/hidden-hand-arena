"""
backtester.py - Hidden Hand: duel two bots on your own machine
===============================================================

    python backtester.py                                 sharp vs reader, 200 deals
    python backtester.py my_bot.py naive --deals 500     your bot vs a house bot
    python backtester.py my_bot.py sharp --show          ...and print one deal, round by round
    python backtester.py --validate my_bot.py            would the arena accept this file?

A bot is a path, or the name of a house bot in strategies/ (naive, reader, sharp).
Every deal is played twice with the hands swapped, so luck cancels out.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bot_loader import check_source, load_for_testing  # noqa: E402
from engine import play_match  # noqa: E402

SUITS = "♠♥♦♣"
FACES = {1: "A", 11: "J", 12: "Q", 13: "K"}


def card(c: int) -> str:
    r = c % 13 + 1
    return f"{FACES.get(r, r)}{SUITS[c // 13]}"


def cards(cs) -> str:
    return " ".join(card(c) for c in cs)


def describe(log: dict) -> str:
    """One deal, as text."""
    n = log["names"]
    out = [f"  {n[0]} holds {cards(log['hands'][0])}",
           f"  {n[1]} holds {cards(log['hands'][1])}",
           f"  board (face down) {cards(log['board'])}"]
    for row in log["rounds"]:
        out.append(f"  -- round {row['round']}  board up: {cards(log['board'][:row['shown']]) or '-'}")
        for i, mv in enumerate(row["moves"]):
            if mv and mv["kind"] == "peek":
                out.append(f"     {n[i]} peeks and sees {card(mv['card'])}")
            elif mv:
                out.append(f"     {n[i]} swaps {card(mv['out'])} for {card(mv['in'])}")
        for q in row["quotes"]:
            m, t = n[q["maker"]], n[1 - q["maker"]]
            px = q["price"]
            act = (f"buys {q['qty']} at {px + 2:g}" if q["qty"] > 0 else
                   f"sells {-q['qty']} at {px - 2:g}" if q["qty"] < 0 else "passes")
            auto = " (no valid quote, house price)" if q["auto"] else ""
            out.append(f"     {m} quotes {px:g}{auto}; {t} {act}")
    out.append(f"  final hands: {n[0]} {cards(log['final_hands'][0])} | {n[1]} {cards(log['final_hands'][1])}")
    out.append(f"  VALUE = {log['V']}   positions {log['positions']}   paid {log['spent']}   PnL {log['pnl']}")
    return "\n".join(out)


def resolve(name: str) -> Path:
    p = Path(name)
    if p.exists():
        return p
    house = HERE / "strategies" / f"{name.removesuffix('.py')}.py"
    if house.exists():
        return house
    sys.exit(f"no such bot: {name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Hidden Hand backtester")
    ap.add_argument("bot1", nargs="?", default="sharp")
    ap.add_argument("bot2", nargs="?", default="reader")
    ap.add_argument("--deals", type=int, default=200, help="deals, each played twice")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--show", action="store_true", help="print the first deal both ways")
    ap.add_argument("--validate", metavar="FILE", help="check a submission and stop")
    args = ap.parse_args()

    if args.validate:
        res = check_source(args.validate)
        print(res.report())
        return 0 if res.ok else 1

    paths = [resolve(args.bot1), resolve(args.bot2)]
    names = (paths[0].stem, paths[1].stem if paths[1].stem != paths[0].stem else paths[1].stem + "2")
    makers = [load_for_testing(p) for p in paths]
    r = play_match(makers[0], makers[1], n_deals=args.deals, seed=args.seed, names=names)

    if args.show:
        for log in r["replays"]:
            print(describe(log) + "\n")
    # Each mirrored pair shares its cards, so the pair is the honest unit of noise.
    pairs = [a + b for a, b in zip(r["per_deal"][::2], r["per_deal"][1::2])]
    mean = statistics.mean(r["per_deal"])
    se = statistics.stdev(pairs) / 2 / len(pairs) ** 0.5 if len(pairs) > 1 else float("nan")
    print(f"{names[0]} vs {names[1]}: {r['deals']} deals")
    print(f"  {names[0]:>12}: score {r['score'][0]:+.3f}   PnL {r['pnl'][0]:+10.1f}  "
          f"{mean:+.2f} per deal  (+- {2 * se:.2f})")
    print(f"  {names[1]:>12}: score {r['score'][1]:+.3f}   PnL {r['pnl'][1]:+10.1f}  "
          f"{r['pnl'][1] / r['deals']:+.2f} per deal")
    print("  (score = what the arena ranks: each deal pair's PnL on a square-root scale, averaged)")
    for name, notes in zip(names, r["notes"]):
        for msg, k in notes.items():
            print(f"  ! {name}: {msg}  (x{k})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
