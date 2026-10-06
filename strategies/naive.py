# Team Name: House - naive
# Members: Organisers
# Mentor: None

"""
naive.py - the baseline. Counts cards, ignores the opponent, never moves.

Fair value = what I can see + (cards I cannot see) x (average unseen rank).
Quotes there, and trades the maximum whenever the price is past the spread.
"""


class Bot:
    def fair(self, obs):
        n = sum(obs.unseen)
        avg = sum((r + 1) * c for r, c in enumerate(obs.unseen)) / n
        hidden = 5 - len(obs.opp_known) + 5 - len(obs.board)
        return sum(obs.hand) + sum(obs.board) + sum(obs.opp_known) + hidden * avg

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
