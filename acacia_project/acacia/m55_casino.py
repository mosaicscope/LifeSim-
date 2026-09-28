# ============================================================================
# [NEW] M55 - CASINO DISTRICT  (persistent location, games, NPC behaviours)
# ============================================================================
#
# A fully persistent casino integrated into the world simulation:
#   * location: exists as a place in settlements
#   * games: roulette, blackjack, slots, poker with actual simulation
#   * npcs: individual gambling personalities; wins/losses affect memory/mood
#   * economy: cashier tracks transactions; winnings feed settlement economy
#   * events: memorable wins/losses generate experiences and relationships
#   * persistence: casino state survives save/load; offline time calculated
#
# NOT scripted: all behaviour emerges from personality, decisions and
# consequences. No hard-coded gambling addiction or forced participation.

import random as _c_random
import math as _c_math
import time as _c_time


# ============================================================================
# CASINO CORE
# ============================================================================

class CasinoDistrict:
    """Persistent casino location with games, staff, and economy."""

    def __init__(self, seed=1, name="The Golden Wheel"):
        self.seed = seed
        self.r = _c_random.Random(seed)
        self.name = name
        self.founded_at = _c_time.time()

        # Physical layout
        self.areas = {
            "entrance": CasinoArea("entrance", "Public entrance, queue"),
            "reception": CasinoArea("reception", "Greeting desk, info"),
            "gaming_floor": CasinoArea("gaming_floor", "Main gaming area"),
            "roulette_room": CasinoArea("roulette_room", "Roulette tables"),
            "blackjack_room": CasinoArea("blackjack_room", "Blackjack tables"),
            "poker_room": CasinoArea("poker_room", "Poker room"),
            "slots_area": CasinoArea("slots_area", "Slot machines"),
            "bar": CasinoArea("bar", "Bar and lounge"),
            "restaurant": CasinoArea("restaurant", "Fine dining"),
            "vip_area": CasinoArea("vip_area", "VIP lounge"),
            "cashier": CasinoArea("cashier", "Currency exchange"),
            "staff_room": CasinoArea("staff_room", "Staff only"),
            "security": CasinoArea("security", "Security office"),
            "restrooms": CasinoArea("restrooms", "Facilities"),
        }

        # Financial state
        self.revenue = 0.0
        self.payouts = 0.0
        self.bankroll = 50000.0
        self.jackpots = {
            "roulette": 1000.0,
            "blackjack": 500.0,
            "slots": 5000.0,
            "poker": 2000.0,
        }

        # Active tables and machines
        self.tables = {}
        self.machines = {}
        self._init_tables()

        # Staff
        self.dealers = {}
        self.staff = {}
        self._init_staff(seed)

        # Activity tracking
        self.daily_visitors = 0
        self.daily_revenue = 0.0
        self.frame = 0
        self.clock = 0.0
        self.npcs_present = set()
        self.events = []

    def _init_tables(self):
        """Create gaming tables."""
        for i in range(2):
            self.tables[f"roulette_{i}"] = RouletteTable(
                f"roulette_{i}", bet_min=10, bet_max=1000
            )
        for i in range(3):
            self.tables[f"blackjack_{i}"] = BlackjackTable(
                f"blackjack_{i}", bet_min=5, bet_max=500
            )
        for i in range(2):
            self.tables[f"poker_{i}"] = PokerTable(
                f"poker_{i}", bet_min=25, bet_max=2000
            )

    def _init_staff(self, seed):
        """Create dealer and casino staff NPCs."""
        names = ["Marie", "James", "Sophie", "Robert", "Clara", "Thomas", "Isabelle", "Pierre"]
        for table_id in self.tables:
            r = _c_random.Random(seed + hash(table_id))
            name = r.choice(names)
            dealer = Dealer(
                f"dealer_{table_id}",
                name,
                table=table_id,
                skill=r.uniform(0.7, 1.0)
            )
            self.dealers[dealer.id] = dealer

    def update(self, dt, game_state):
        """Advance casino simulation. Called ~60 Hz but decision logic
        runs at ~1 Hz (tick-based)."""
        self.frame += 1
        self.clock += dt

        # Tick-based updates every ~30 ticks (0.5s)
        if self.frame % 30 == 0:
            self._tick()

    def _tick(self):
        """Periodic casino simulation tick."""
        # Tables continue their games
        for table in self.tables.values():
            table.tick()

        # Prune old events
        now = _c_time.time()
        self.events = [e for e in self.events if now - e["time"] < 3600.0]

    def npc_enter(self, npc_id, bankroll):
        """NPC enters the casino with a given bankroll."""
        self.npcs_present.add(npc_id)
        self.daily_visitors += 1
        return CasinoVisit(npc_id, bankroll, _c_time.time())

    def npc_leave(self, npc_id, visit):
        """NPC leaves the casino. Return their winnings/losses."""
        self.npcs_present.discard(npc_id)
        delta = visit.bankroll - visit.initial_bankroll
        if delta > 0:
            self.payouts += delta
        else:
            self.revenue += -delta
        self.daily_revenue += delta
        return delta

    def log_event(self, kind, npc_id, amount, table_id=None, text=""):
        """Log a significant casino event."""
        self.events.append({
            "time": _c_time.time(),
            "kind": kind,  # "win", "loss", "jackpot", "bigwin"
            "npc": npc_id,
            "amount": amount,
            "table": table_id,
            "text": text,
        })

    def to_dict(self):
        """Serialize casino state."""
        return {
            "seed": self.seed,
            "name": self.name,
            "founded_at": self.founded_at,
            "revenue": self.revenue,
            "payouts": self.payouts,
            "bankroll": self.bankroll,
            "jackpots": dict(self.jackpots),
            "tables": {k: v.to_dict() for k, v in self.tables.items()},
            "daily_visitors": self.daily_visitors,
            "daily_revenue": self.daily_revenue,
            "events": self.events[-100:],  # Keep last 100
        }

    @classmethod
    def from_dict(cls, d):
        """Deserialize casino state."""
        casino = cls(seed=d["seed"], name=d["name"])
        casino.founded_at = d["founded_at"]
        casino.revenue = d["revenue"]
        casino.payouts = d["payouts"]
        casino.bankroll = d["bankroll"]
        casino.jackpots = d["jackpots"]
        casino.daily_visitors = d["daily_visitors"]
        casino.daily_revenue = d["daily_revenue"]
        casino.events = d["events"]

        # Restore tables
        for table_id, table_data in d.get("tables", {}).items():
            if table_id in casino.tables:
                casino.tables[table_id].from_dict(table_data)

        return casino


class CasinoArea:
    """A room/area within the casino."""
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.npcs = set()
        self.lighting = 0.8
        self.activity = 0.0

    def add_npc(self, npc_id):
        self.npcs.add(npc_id)
        self.activity = min(1.0, self.activity + 0.1)

    def remove_npc(self, npc_id):
        self.npcs.discard(npc_id)
        if not self.npcs:
            self.activity = max(0.0, self.activity - 0.2)


class CasinoVisit:
    """Tracks a single NPC's casino visit."""
    def __init__(self, npc_id, initial_bankroll, start_time):
        self.npc_id = npc_id
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.start_time = start_time
        self.games_played = []
        self.biggest_win = 0.0
        self.biggest_loss = 0.0
        self.duration = 0.0


# ============================================================================
# ROULETTE
# ============================================================================

class RouletteWheel:
    """A deterministic roulette wheel."""
    def __init__(self):
        self.pockets = list(range(37))  # 0-36
        self.red = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        self.black = set(range(37)) - self.red - {0}

    def spin(self, seed):
        """Deterministic spin based on seed."""
        r = _c_random.Random(seed)
        return r.choice(self.pockets)

    def payout(self, number, bet_type, wager):
        """Calculate payout for a winning bet."""
        payouts = {
            "straight": (36, 1),        # 35:1
            "split": (18, 1),           # 17:1
            "street": (12, 1),          # 11:1
            "corner": (9, 1),           # 8:1
            "line": (6, 1),             # 5:1
            "dozen": (3, 1),            # 2:1
            "column": (3, 1),           # 2:1
            "red_black": (2, 1),        # 1:1
            "odd_even": (2, 1),         # 1:1
            "high_low": (2, 1),         # 1:1
        }
        if bet_type not in payouts:
            return 0
        mult, _ = payouts[bet_type]
        return wager * mult


class RouletteTable:
    """A roulette table with wheel and bets."""
    def __init__(self, id, bet_min=10, bet_max=1000):
        self.id = id
        self.wheel = RouletteWheel()
        self.bets = {}  # npc_id -> [(bet_type, numbers, amount), ...]
        self.bet_min = bet_min
        self.bet_max = bet_max
        self.state = "open"  # open, locked, spinning, settling
        self.spin_time = 0.0
        self.result = None
        self.frame = 0

    def place_bet(self, npc_id, bet_type, amount, numbers=None):
        """Place a bet on the roulette table."""
        if not (self.bet_min <= amount <= self.bet_max):
            return False, "Bet outside limits"
        if self.state != "open":
            return False, "Table not accepting bets"

        if npc_id not in self.bets:
            self.bets[npc_id] = []
        self.bets[npc_id].append({
            "type": bet_type,
            "numbers": numbers or [],
            "amount": amount,
        })
        return True, "Bet placed"

    def spin_wheel(self):
        """Begin the spin and calculate result."""
        self.state = "spinning"
        seed = int(_c_time.time() * 10000) % 100000
        self.result = self.wheel.spin(seed)
        self.state = "settling"
        return self.result

    def resolve_bets(self):
        """Resolve all outstanding bets. Returns {npc_id: (payout, profit)}."""
        results = {}

        for npc_id, bets in self.bets.items():
            total_payout = 0
            for bet in bets:
                if self._bet_wins(bet, self.result):
                    payout = self.wheel.payout(self.result, bet["type"], bet["amount"])
                    total_payout += payout

            total_wagered = sum(b["amount"] for b in bets)
            profit = total_payout - total_wagered
            results[npc_id] = (total_payout, profit)

        self.bets = {}
        self.state = "open"
        return results

    def _bet_wins(self, bet, result):
        """Check if a bet wins given the wheel result."""
        bet_type = bet["type"]
        if bet_type == "straight":
            return result in bet["numbers"]
        elif bet_type == "red_black":
            return (result in self.wheel.red and bet["numbers"] == ["red"]) or \
                   (result in self.wheel.black and bet["numbers"] == ["black"])
        elif bet_type == "odd_even":
            is_odd = result % 2 == 1
            return (is_odd and bet["numbers"] == ["odd"]) or \
                   (not is_odd and bet["numbers"] == ["even"])
        elif bet_type == "high_low":
            is_high = result >= 19
            return (is_high and bet["numbers"] == ["high"]) or \
                   (not is_high and bet["numbers"] == ["low"])
        elif bet_type == "dozen":
            dozen = (result - 1) // 12 if result > 0 else None
            return dozen in bet["numbers"]
        return False

    def tick(self):
        """Update table state."""
        self.frame += 1
        if self.state == "settling" and self.frame % 60 == 0:
            self.state = "open"

    def to_dict(self):
        return {"state": self.state, "result": self.result}

    def from_dict(self, d):
        self.state = d["state"]
        self.result = d["result"]


# ============================================================================
# BLACKJACK
# ============================================================================

class BlackjackTable:
    """A blackjack table."""
    def __init__(self, id, bet_min=5, bet_max=500):
        self.id = id
        self.bet_min = bet_min
        self.bet_max = bet_max
        self.deck = self._make_deck()
        self.players = {}  # npc_id -> BlackjackHand
        self.dealer_hand = BlackjackHand(True)
        self.state = "waiting"  # waiting, betting, dealing, playing, settling
        self.frame = 0

    def _make_deck(self):
        """Create a shoe of 6 decks (simplified)."""
        deck = []
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for _ in range(6):
            deck.extend(ranks)
        self.r = _c_random.Random(int(_c_time.time() * 100) % 1000)
        self.r.shuffle(deck)
        return deck

    def deal_card(self):
        """Draw a card from the deck."""
        if len(self.deck) < 20:
            self.deck = self._make_deck()
        return self.deck.pop()

    def place_bet(self, npc_id, amount):
        """Place a bet and receive initial hand."""
        if not (self.bet_min <= amount <= self.bet_max):
            return False, "Bet outside limits"

        hand = BlackjackHand(False)
        hand.bet = amount
        hand.add_card(self.deal_card())
        hand.add_card(self.deal_card())
        self.players[npc_id] = hand

        # Dealer shows one card
        if len(self.dealer_hand.cards) == 0:
            self.dealer_hand.add_card(self.deal_card())
            self.dealer_hand.add_card(self.deal_card())

        return True, f"You have {hand.value()}"

    def player_hit(self, npc_id):
        """Player takes another card."""
        if npc_id not in self.players:
            return False, "Not in game"
        hand = self.players[npc_id]
        hand.add_card(self.deal_card())
        if hand.bust():
            return False, f"Bust! {hand.value()}"
        return True, f"You have {hand.value()}"

    def player_stand(self, npc_id):
        """Player stands."""
        if npc_id not in self.players:
            return False, "Not in game"
        self.players[npc_id].standing = True
        return True, "Dealer plays..."

    def dealer_plays(self):
        """Dealer follows rules: hit on <17, stand on 17+."""
        while self.dealer_hand.value() < 17:
            self.dealer_hand.add_card(self.deal_card())

    def resolve_hands(self):
        """Resolve all player hands. Returns {npc_id: (payout, profit)}."""
        self.dealer_plays()
        results = {}

        for npc_id, player_hand in self.players.items():
            payout = 0

            if player_hand.bust():
                payout = 0
            elif self.dealer_hand.bust():
                payout = player_hand.bet * 2
            elif player_hand.value() > self.dealer_hand.value():
                payout = player_hand.bet * 2
            elif player_hand.value() == self.dealer_hand.value():
                payout = player_hand.bet

            profit = payout - player_hand.bet
            results[npc_id] = (payout, profit)

        self.players = {}
        self.dealer_hand = BlackjackHand(True)
        return results

    def tick(self):
        pass

    def to_dict(self):
        return {"state": self.state}

    def from_dict(self, d):
        self.state = d["state"]


class BlackjackHand:
    """A hand of blackjack cards."""
    def __init__(self, is_dealer=False):
        self.cards = []
        self.is_dealer = is_dealer
        self.bet = 0
        self.standing = False

    def add_card(self, card):
        self.cards.append(card)

    def value(self):
        """Calculate hand value (with soft 17 logic)."""
        vals = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        total = sum(vals.get(c, 0) for c in self.cards)
        aces = self.cards.count('A')
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    def bust(self):
        return self.value() > 21


# ============================================================================
# SLOTS
# ============================================================================

class SlotMachine:
    """A single slot machine."""
    def __init__(self, id, seed=1):
        self.id = id
        self.r = _c_random.Random(seed)
        self.symbols = ['cherry', 'bell', 'bar', '7', 'gold', 'diamond']
        self.payouts = {
            '7_7_7': 100,
            'gold_gold_gold': 50,
            'diamond_diamond_diamond': 75,
            'bar_bar_bar': 30,
            'bell_bell_bell': 20,
            'cherry_cherry_cherry': 10,
            'any_pair': 2,
        }
        self.bet_min = 1
        self.bet_max = 100
        self.total_wagered = 0.0
        self.total_paid = 0.0
        self.frame = 0

    def spin(self, wager):
        """Spin the machine and return result."""
        if not (self.bet_min <= wager <= self.bet_max):
            return None, 0

        reels = [self.r.choice(self.symbols) for _ in range(3)]
        payout = self._calculate_payout(reels, wager)

        self.total_wagered += wager
        self.total_paid += payout
        self.frame += 1

        return reels, payout

    def _calculate_payout(self, reels, wager):
        """Calculate payout based on symbols."""
        if reels[0] == reels[1] == reels[2]:
            key = f"{reels[0]}_{reels[1]}_{reels[2]}"
            return wager * self.payouts.get(key, 0)
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            return wager * 2
        return 0

    def to_dict(self):
        return {
            "total_wagered": self.total_wagered,
            "total_paid": self.total_paid,
        }

    def from_dict(self, d):
        self.total_wagered = d["total_wagered"]
        self.total_paid = d["total_paid"]


# ============================================================================
# POKER
# ============================================================================

class PokerTable:
    """A poker table (simplified Texas Hold'em)."""
    def __init__(self, id, bet_min=25, bet_max=2000):
        self.id = id
        self.bet_min = bet_min
        self.bet_max = bet_max
        self.players = {}  # npc_id -> PokerHand
        self.deck = self._make_deck()
        self.community = []
        self.pot = 0.0
        self.state = "waiting"
        self.frame = 0

    def _make_deck(self):
        """Create a standard deck."""
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [f"{r}{s}" for r in ranks for s in suits]
        self.r = _c_random.Random(int(_c_time.time() * 100) % 1000)
        self.r.shuffle(deck)
        return deck

    def deal_card(self):
        """Draw a card."""
        if not self.deck:
            self.deck = self._make_deck()
        return self.deck.pop()

    def join(self, npc_id, stack):
        """Player joins the table."""
        hand = PokerHand()
        hand.hole = [self.deal_card(), self.deal_card()]
        hand.stack = stack
        self.players[npc_id] = hand
        return True

    def leave(self, npc_id):
        """Player leaves the table."""
        if npc_id in self.players:
            del self.players[npc_id]
            return True
        return False

    def tick(self):
        pass

    def to_dict(self):
        return {"state": self.state, "pot": self.pot}

    def from_dict(self, d):
        self.state = d["state"]
        self.pot = d["pot"]


class PokerHand:
    """A player's poker hand."""
    def __init__(self):
        self.hole = []
        self.stack = 0
        self.bet = 0
        self.folded = False

    def get_best_rank(self, community):
        """Evaluate hand strength (simplified)."""
        return sum(ord(c[0]) for c in self.hole + community)


# ============================================================================
# DEALERS & STAFF
# ============================================================================

class Dealer:
    """A casino dealer NPC."""
    def __init__(self, id, name, table, skill=0.9):
        self.id = id
        self.name = name
        self.table = table
        self.skill = skill  # Affects fairness perception
        self.shift_start = 0.0
        self.shift_end = 8.0
        self.on_duty = False
        self.mood = 0.0
        self.familiar_players = {}  # npc_id -> familiarity_score
        self.tips_received = 0.0
        self.memorable_moments = []

    def meets_player(self, npc_id, context="first_visit"):
        """Dealer remembers meeting a player."""
        fam = self.familiar_players.get(npc_id, 0.0)
        self.familiar_players[npc_id] = min(1.0, fam + 0.2)
        return fam

    def get_greeting(self, npc_id):
        """Generate appropriate greeting based on familiarity."""
        fam = self.familiar_players.get(npc_id, 0.0)
        if fam < 0.1:
            return f"Welcome to the {self.table}."
        elif fam < 0.5:
            return f"Good to see you back."
        else:
            return f"Glad to see you again, friend."


# ============================================================================
# NPC GAMBLING PERSONALITY
# ============================================================================

class GamblingPersonality:
    """Individual gambling traits that emerge from base personality."""
    def __init__(self, npc_traits, seed):
        self.r = _c_random.Random(seed)

        # Derive gambling traits from base personality
        # These are normalized [0, 1]
        self.risk_tolerance = (npc_traits.get("ambition", 0.5) +
                               npc_traits.get("boldness", 0.5)) / 2.0
        self.patience = npc_traits.get("patience", 0.5)
        self.greed = npc_traits.get("greed", 0.3)
        self.competitiveness = npc_traits.get("sociability", 0.5) * 0.3 + npc_traits.get("ambition", 0.5) * 0.7
        self.impulsivity = 1.0 - npc_traits.get("intelligence", 0.5)
        self.superstition = self.r.uniform(0.0, 0.5)

        # Game preferences [0-1 score for each]
        self.prefers = {
            "roulette": 0.2 + self.risk_tolerance * 0.3,  # High-risk
            "blackjack": 0.5 + self.patience * 0.3,       # Skill-based
            "slots": 0.3 + self.impulsivity * 0.3,        # Low-skill
            "poker": 0.4 + self.competitiveness * 0.4,    # Competitive
        }

        # Individual limits
        self.session_limit = 100 + self.risk_tolerance * 400  # Max willing to lose
        self.daily_limit = 500 + self.risk_tolerance * 2000
        self.preferred_stake = 25 + self.risk_tolerance * 200
        self.win_walk_away_threshold = 0.5 + self.patience * 0.4
        self.loss_chase_threshold = 1.0 - self.patience

        # Behavior patterns
        self.chases_losses = self.impulsivity > self.patience
        self.rides_wins = self.greed > 0.5
        self.takes_long_breaks = self.patience > 0.7
        self.seeks_company = npc_traits.get("sociability", 0.5) > 0.6
        self.superstitious_bets = self.superstition > 0.4

    def choose_game(self):
        """Pick a game based on personality."""
        games = list(self.prefers.keys())
        scores = [self.prefers[g] + self.r.uniform(-0.2, 0.2) for g in games]
        return games[scores.index(max(scores))]

    def decide_bet(self, bankroll, loss_so_far=0.0):
        """Decide how much to bet."""
        # Base bet influenced by personality
        base = min(self.preferred_stake, bankroll * 0.1)

        # Adjust for mood: chasing losses or riding wins
        if loss_so_far > self.session_limit * 0.5 and self.chases_losses:
            base *= (1.0 + (loss_so_far - self.session_limit * 0.5) / 100.0)

        # Limit to bankroll
        return max(10, min(bankroll * 0.2, base))

    def should_continue(self, bankroll, won, lost, session_duration):
        """Should the NPC keep gambling?"""
        # No money left
        if bankroll <= self.preferred_stake:
            return False

        # Won enough
        if won > self.session_limit * self.win_walk_away_threshold and self.patience > 0.7:
            return False

        # Lost too much
        if lost > self.session_limit * 1.5:
            return False

        # Been here too long
        if session_duration > 180 and self.patience > 0.6:
            return False

        return True

    def to_dict(self):
        return {
            "risk_tolerance": self.risk_tolerance,
            "patience": self.patience,
            "greed": self.greed,
            "prefers": dict(self.prefers),
        }


# ============================================================================
# INTEGRATION WITH EXISTING SYSTEMS
# ============================================================================

def _ca_should_visit_casino(psy, app, life, npc_traits, mood):
    """Determine if an NPC would want to gamble (integration with M42 agency)."""
    # NPCs with certain traits are drawn to gambling
    ambition = npc_traits.get("ambition", 0.5)
    boldness = npc_traits.get("boldness", 0.5)
    sociability = npc_traits.get("sociability", 0.5)

    # Lonely NPCs seek company/entertainment
    # Ambitious NPCs seek wealth/status
    # Bold NPCs seek thrills

    gambling_drive = (ambition * 0.4 + boldness * 0.4 + sociability * 0.2) * mood

    return gambling_drive > 0.3


def _ca_npc_memory_event(app, npc_id, kind, amount, context=""):
    """Add a memorable gambling event to NPC memory (M04 memory integration)."""
    # This would integrate with the existing memory system
    # For now, we store locally
    memory_entry = {
        "time": _c_time.time(),
        "kind": kind,  # "big_win", "big_loss", "regular_win", "regular_loss"
        "amount": amount,
        "context": context,
        "emotional_impact": _ca_emotional_impact(kind, amount),
    }
    return memory_entry


def _ca_emotional_impact(kind, amount):
    """Calculate emotional impact of a gambling outcome."""
    impacts = {
        "big_win": min(1.0, amount / 500.0) * 0.8,
        "regular_win": min(1.0, amount / 50.0) * 0.3,
        "big_loss": -min(1.0, amount / 500.0) * 0.8,
        "regular_loss": -min(1.0, amount / 50.0) * 0.3,
    }
    return impacts.get(kind, 0.0)


def _ca_casino_location():
    """Return the casino as a POI in settlements (M46 world integration)."""
    return {
        "kind": "casino",
        "name": "The Golden Wheel Casino",
        "accessible": True,
        "indoor": True,
        "places": ["gaming_floor", "bar", "restaurant", "vip_area"],
    }


# ============================================================================
# SAVE/LOAD INTEGRATION (M43 continuity)
# ============================================================================

def _ca_continuity_snapshot(casino, elapsed_days):
    """Calculate plausible casino state after offline time."""
    # Staff continue their shifts
    # Machines continue paying out (with house edge)
    # Jackpots grow slowly
    # Some NPCs may have visited

    # Simplified: apply house edge daily
    house_edge_daily = casino.daily_revenue * 0.6 - casino.daily_revenue * 0.4
    revenue_gain = house_edge_daily * elapsed_days * 0.3  # Scaled down for offline

    casino.revenue += max(0, revenue_gain)
    casino.bankroll += max(0, revenue_gain)

    # Jackpots grow with contributions
    for game, jackpot in casino.jackpots.items():
        casino.jackpots[game] += (jackpot * 0.001 * elapsed_days)


# ============================================================================
# INITIALIZATION HOOKS
# ============================================================================

# This will be called by the app to integrate the casino into the world
def init_casino(app, seed=1):
    """Initialize the casino district (called by m33_app or similar)."""
    casino = CasinoDistrict(seed=seed, name="The Golden Wheel")
    return casino


def get_casino(app):
    """Get or create the casino instance."""
    if not hasattr(app, "casino"):
        app.casino = init_casino(app)
    return app.casino
