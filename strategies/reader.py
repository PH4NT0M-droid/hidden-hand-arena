# Team Name: House - reader
# Members: Organisers
# Mentor: None

"""
reader.py - naive, plus it reads the opponent's quotes.

An honest maker quotes its own fair value: its hand + the board + its unknown
cards x the average unseen rank. Everything in that sum is public except its
hand, so its quote gives its hand away. Run the formula backwards to get an
estimate of the opponent's hand, then trust it most of the way.
"""

TRUST = 0.8      # how far to move from "average hand" towards what the quote implies


class Bot:
    def avg(self, obs):
        return sum((r + 1) * c for r, c in enumerate(obs.unseen)) / sum(obs.unseen)

    def fair(self, obs):
        m = self.avg(obs)
        hidden_board = 5 - len(obs.board)
        opp_hand = sum(obs.opp_known) + (5 - len(obs.opp_known)) * m
        theirs = [px for r, who, px, q in obs.tape if who == "opp"]
        if theirs:
            # Their unknowns, as they see it: my 5 cards and the hidden board.
            # (The board may have turned since they quoted; close enough.)
            implied = theirs[-1] - sum(obs.board) - (5 + hidden_board) * m
            opp_hand += TRUST * (implied - opp_hand)
        return sum(obs.hand) + sum(obs.board) + opp_hand + hidden_board * m

    def move(self, obs):
        return None

    def quote(self, obs):
        return self.fair(obs)

    def respond(self, obs, price):
        edge = self.fair(obs) - price
        if edge > 2:
            return 2
        if edge < -2:
            return -2
        return 0
