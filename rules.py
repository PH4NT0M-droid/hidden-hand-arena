"""
rules.py - Hidden Hand: every number in the game, and what a bot is shown
==========================================================================

Constants and the Obs your bot receives, nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── The deck ───────────────────────────────────────────────
# One standard 52-card deck. A card is worth its rank: A=1, 2..10, J=11, Q=12, K=13.
RANKS = 13
COPIES = 4                     # four suits of every rank
HAND_SIZE = 5                  # private cards per player
BOARD_SIZE = 5                 # face-down community cards

# The stock settles at the sum of BOTH hands plus the whole board:
# 15 cards, worth 105 on average.

# ── A deal ─────────────────────────────────────────────────
ROUNDS = 5                     # board card r-1 is turned face up at the start of round r
PEEK_COST = 3.0                # PEEK: see one random card of the opponent's hand
SWAP_COST = 0.0                # SWAP: discard a card face up, draw a fresh one
MAX_SWAPS = 1                  # swaps allowed per player per deal

# ── Trading ────────────────────────────────────────────────
HALF_SPREAD = 2.0              # the taker buys at price + 2 or sells at price - 2
MAX_LOT = 2                    # most lots a taker can trade on one quote
POSITION_LIMIT = 10            # nobody may hold more than this, long or short
NO_QUOTE_PRICE = 105.0         # a maker that fails to quote is quoted here for it
MAX_PRICE = RANKS * (2 * HAND_SIZE + BOARD_SIZE)

# ── Limits ─────────────────────────────────────────────────
HARD_TIME_LIMIT_MS = 50.0      # one call, worst case

# ── What a submission may import ───────────────────────────
ALLOWED_MODULES = frozenset({
    "math", "random", "statistics", "collections", "heapq",
    "bisect", "itertools", "functools", "typing",
})
# Pulled in by ordinary syntax (`from __future__ import ...`, typing.NamedTuple).
IMPORTABLE_MODULES = ALLOWED_MODULES | {"__future__", "annotationlib"}


@dataclass(frozen=True)
class Obs:
    """Everything your bot knows when it is asked to act. Cards are ranks 1..13.

    tape:     every quote so far, oldest first: (round, maker, price, qty).
              maker is "me" or "opp"; qty is what the taker did
              (+3 = bought 3 at price + 2, -3 = sold 3 at price - 2, 0 = passed).
    discards: every swapped-out card, face up: (round, who, rank).
    peeks:    every peek so far: (round, who). Nobody learns WHICH card was seen.
    """
    round: int                 # 1 .. ROUNDS
    hand: tuple                # your 5 cards right now
    board: tuple               # board cards turned face up so far
    opp_known: tuple           # opponent cards you have peeked that they still hold
    unseen: tuple              # unseen[r-1] = copies of rank r you have not seen anywhere
    position: int              # lots you hold: + long, - short
    cash: float                # money from your trades so far
    spent: float               # what you have paid for peeks and swaps
    tape: tuple
    discards: tuple
    peeks: tuple
