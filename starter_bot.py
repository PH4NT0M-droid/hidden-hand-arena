# Team Name: [your team name]
# Members: [Name 1 (Roll No.), Name 2 (Roll No.), Name 3 (Roll No.)]
# Mentor: [your mentor's name]

"""
starter_bot.py - Hidden Hand: copy this file, rename it, make it yours.

A fresh Bot() is built for every deal, so anything you store on self lasts
exactly one deal. Three methods, each called with an Obs (see rules.py):

    move(obs)            once per round, before trading:
                           None          do nothing
                           "PEEK"        pay 3, see one random card of their hand
                           ("SWAP", i)   discard obs.hand[i] face up, draw a new card
                                         (once per deal)
    quote(obs)           you are the maker: name a price. They may buy from
                         you at price + 2 or sell to you at price - 2.
    respond(obs, price)  they quoted price: return how many lots to trade,
                         +n to buy n at price + 2, -n to sell n at price - 2,
                         0 to pass. At most 2 lots, and your position stays
                         within +-10.

The stock settles at the sum of all 15 cards: your hand, their hand and the
whole board (A=1 ... K=13). As written, this bot IS the house's `naive` bot:
it scores exactly 0 against it, so there is everything left to win.
"""


class Bot:
    def fair(self, obs):
        """My best guess of the final value, from cards alone.

        Known cards count at face value. Every card I cannot see (their hand
        and the face-down board) is worth the average of the ranks I have not
        seen yet: card counting, because the deck has no replacement.
        """
        unseen = sum(obs.unseen)
        avg = sum((r + 1) * c for r, c in enumerate(obs.unseen)) / unseen
        hidden = (5 - len(obs.opp_known)) + (5 - len(obs.board))
        return sum(obs.hand) + sum(obs.board) + sum(obs.opp_known) + hidden * avg

    def move(self, obs):
        # Ideas: does it pay to peek? If you are long, what does swapping your
        # lowest card do to the value you are long of? What can the opponent's
        # discards and peeks tell you?
        return None

    def quote(self, obs):
        # Your quote tells the opponent about your hand. Is that a problem?
        return self.fair(obs)

    def respond(self, obs, price):
        # The opponent's price tells you about THEIR hand. Use it.
        edge = self.fair(obs) - price
        if edge > 2:
            return 2
        if edge < -2:
            return -2
        return 0
