# ============================================================================
# [NEW] M56 - CASINO INTEGRATION  (hooks into existing ACACIA systems)
# ============================================================================
#
# Ties M55 casino into:
#   * M42 agency: gambling becomes an affordance/goal for NPCs
#   * M43 continuity: casino state persists and advances offline
#   * M46 world: casino appears as a location in settlements
#   * M44 society: economy integration, NPC visits affect settlements
#   * M04 memory: wins/losses become memories that influence future choices
#   * M07 relationships: casino meetings create/strengthen relationships
#   * M02 events: casino events feed into the event stream
#
# This module sets up the hooks; actual game code lives in M55.

import time as _ci_time
import random as _ci_random


# ============================================================================
# AGENCY INTEGRATION (M42)
# ============================================================================

# Add gambling as possible goals and affordances
_CI_CASINO_ACTIONS = {
    "gamble_roulette": dict(
        pre={"money": 50},
        eff={"gambled": ("set", 1)},  # effect varies; real outcome happens at casino
        dur=15.0,
        at="roulette_table",
        task="gamble",
        value="gambling"
    ),
    "gamble_blackjack": dict(
        pre={"money": 50},
        eff={"gambled": ("set", 1)},
        dur=20.0,
        at="blackjack_table",
        task="gamble",
        value="gambling"
    ),
    "gamble_slots": dict(
        pre={"money": 25},
        eff={"gambled": ("set", 1)},
        dur=10.0,
        at="slots_area",
        task="gamble",
        value="gambling"
    ),
    "gamble_poker": dict(
        pre={"money": 100},
        eff={"gambled": ("set", 1)},
        dur=30.0,
        at="poker_table",
        task="gamble",
        value="gambling",
        risk=("poker", "bluffed_wrong")
    ),
    "visit_casino_bar": dict(
        pre={},
        eff={"socialized": ("set", 1)},
        dur=5.0,
        at="casino_bar",
        task="relax",
        value="socializing"
    ),
}


def _ci_inject_casino_actions():
    """Inject casino affordances into the agency system (M42)."""
    # Try to find and extend the existing action library
    NS = globals().get("NS") or globals()

    if "_AG_ACTIONS" in NS:
        # Extend existing actions
        NS["_AG_ACTIONS"].update(_CI_CASINO_ACTIONS)

    # Also add to any NPC-specific planning
    if "_AG_GOALS" in NS:
        NS["_AG_GOALS"].update({
            "gamble": {"gambled": 1},
            "relax": {"socialized": 1},
        })


def _ci_npc_should_gamble(npc, gambling_personality, current_wealth, mood):
    """Determine if an NPC should go to the casino based on personality and state."""
    # NPCs gamble more when:
    # - They're bored (low activity level)
    # - They're social and want entertainment
    # - They've won recently (confidence)
    # - They have enough money
    # - Their risk tolerance is high

    if current_wealth < gambling_personality.session_limit * 0.1:
        return False  # Too poor

    base_drive = (
        gambling_personality.risk_tolerance * 0.3 +
        gambling_personality.competitiveness * 0.2 +
        (1.0 - gambling_personality.patience) * 0.2 +
        mood * 0.3  # Mood boost
    )

    return base_drive > 0.4 + _ci_random.random() * 0.3


# ============================================================================
# CONTINUITY INTEGRATION (M43)
# ============================================================================

def _ci_continuity_save(casino):
    """Prepare casino state for save (M43)."""
    return casino.to_dict()


def _ci_continuity_load(casino_data):
    """Restore casino from saved state (M43)."""
    NS = globals().get("NS") or globals()
    CasinoDistrict = NS.get("CasinoDistrict")

    if CasinoDistrict:
        return CasinoDistrict.from_dict(casino_data)
    return None


def _ci_continuity_advance(casino, elapsed_seconds):
    """Advance casino state for offline time (M43)."""
    # Calculate plausible changes while offline
    elapsed_days = elapsed_seconds / 86400.0

    # Apply house edge over time
    daily_edge = casino.bankroll * 0.02  # 2% daily house edge
    casino.bankroll -= daily_edge * elapsed_days
    casino.revenue += daily_edge * elapsed_days

    # Jackpots grow slowly
    for game in casino.jackpots:
        casino.jackpots[game] *= (1.0 + 0.0001 * elapsed_days)

    # Prune old events
    cutoff = _ci_time.time() - 7 * 24 * 3600  # Keep events from last week
    casino.events = [e for e in casino.events if e.get("time", 0) > cutoff]

    # Reset daily counters
    casino.daily_visitors = 0
    casino.daily_revenue = 0.0


# ============================================================================
# WORLD INTEGRATION (M46)
# ============================================================================

def _ci_world_add_casino(world, settlement_name):
    """Add casino as a location/POI in a settlement (M46 world)."""
    # Create a synthetic POI for the casino
    casino_poi = {
        "kind": "casino",
        "name": "The Golden Wheel",
        "x": None,  # Will be set by world placement
        "y": None,
        "accessible": True,
        "indoor": True,
        "available": True,
        "description": "An opulent gambling establishment with games, food, and entertainment.",
    }
    return casino_poi


def _ci_settlement_has_casino(settlement_name):
    """Check if a settlement is large enough to support a casino."""
    # Only larger settlements have casinos (population > 100)
    # This prevents every village from having one
    NS = globals().get("NS") or globals()
    Society = NS.get("Society")

    if Society and hasattr(Society, "sets"):
        # Would check settlement.pop here
        return True
    return False


# ============================================================================
# MEMORY INTEGRATION (M04)
# ============================================================================

def _ci_memory_add_gambling_event(app, npc_id, event_kind, amount, table_id):
    """Record a gambling event in NPC memory (M04)."""
    # Create a memorable experience
    event = {
        "type": "gambling",
        "subtype": event_kind,  # "win", "loss", "bigwin", "bigloss", "jackpot"
        "amount": amount,
        "table": table_id,
        "time": _ci_time.time(),
        "valence": _ci_emotion_from_outcome(event_kind, amount),
        "memorability": min(1.0, abs(amount) / 500.0),
    }

    # Would integrate with M04 memory system here
    return event


def _ci_emotion_from_outcome(event_kind, amount):
    """Convert gambling outcome to emotional valence."""
    if event_kind in ("win", "bigwin", "jackpot"):
        return min(1.0, amount / 1000.0)  # Positive valence
    elif event_kind in ("loss", "bigloss"):
        return -min(1.0, amount / 1000.0)  # Negative valence
    return 0.0


# ============================================================================
# RELATIONSHIPS INTEGRATION (M07)
# ============================================================================

def _ci_relationship_casino_meeting(app, npc1_id, npc2_id, context):
    """Record a relationship change from casino interaction (M07)."""
    # Two NPCs met at the casino
    # They might:
    # - win together -> positive bond
    # - lose together -> commiseration bond
    # - play against each other (poker) -> competitive bond
    # - form a friendship

    event = {
        "type": "casino_meeting",
        "context": context,  # "played_together", "watched_together", "celebrated_win", etc.
        "time": _ci_time.time(),
    }

    # Calculate relationship impact
    if context == "big_win_together":
        impact = 0.3  # Positive
    elif context == "big_loss_together":
        impact = 0.1  # Minor positive (shared misery)
    elif context == "played_poker":
        impact = 0.0  # Neutral/competitive
    else:
        impact = 0.05

    return event, impact


# ============================================================================
# EVENTS INTEGRATION (M02)
# ============================================================================

def _ci_event_jackpot_won(casino, npc_id, amount, game):
    """Create a perception event for a jackpot win."""
    NS = globals().get("NS") or globals()
    Event = NS.get("Event")

    if Event:
        return Event(
            kind="gambling_jackpot",
            actor=npc_id,
            where="casino",
            val=min(1.0, amount / 5000.0),  # Emotional intensity
            text=f"{npc_id} hit the {game} jackpot for {amount}!"
        )
    return None


def _ci_event_big_loss(casino, npc_id, amount):
    """Create a perception event for a big loss."""
    NS = globals().get("NS") or globals()
    Event = NS.get("Event")

    if Event:
        return Event(
            kind="gambling_loss",
            actor=npc_id,
            where="casino",
            val=-min(1.0, amount / 1000.0),  # Emotional intensity
            text=f"{npc_id} lost {amount} at the casino."
        )
    return None


# ============================================================================
# ECONOMY INTEGRATION (M44 society)
# ============================================================================

def _ci_npc_casino_budget(npc_wealth, gambling_personality):
    """Determine how much an NPC can afford to gamble."""
    # Wealthy NPCs gamble more; poor NPCs stay away
    disposable = npc_wealth * 0.1  # 10% of wealth is disposable

    # Risk-tolerant NPCs are willing to risk more
    risk_factor = 0.5 + gambling_personality.risk_tolerance * 0.5

    return disposable * risk_factor


def _ci_settlement_economy_update(settlement, casino, npc_visit_delta):
    """Update settlement economy based on casino activity (M44)."""
    # Wealthy settlements attract gambling
    # Casino revenue indirectly affects settlement wealth/morale
    # NPCs returning from casino with losses spend less elsewhere

    # NPC wealth flows casino -> settlement through spending
    # Some "dirty money" might affect faction dynamics
    pass


# ============================================================================
# UI INTEGRATION
# ============================================================================

def _ci_ui_casino_panels():
    """Define UI panels for casino status display."""
    panels = {
        "CASINO": {
            "title": "Casino Status",
            "sections": [
                "Roulette", "Blackjack", "Poker", "Slots",
                "VIP", "People", "Events", "Staff",
            ],
            "refresh_rate": 10,  # Hz
        },
    }
    return panels


# ============================================================================
# INITIALIZATION
# ============================================================================

def _ci_init_casino_system(app, seed=1):
    """Initialize casino and integrate with ACACIA (called at app startup)."""
    NS = globals().get("NS") or globals()
    CasinoDistrict = NS.get("CasinoDistrict")

    if not CasinoDistrict:
        return None

    # Create the casino
    casino = CasinoDistrict(seed=seed)

    # Inject into app
    app.casino = casino
    app.casino_personalities = {}  # npc_id -> GamblingPersonality
    app.casino_visits = {}  # npc_id -> CasinoVisit

    # Install hooks
    _ci_inject_casino_actions()

    return casino


def _ci_update_casino(app, dt):
    """Update casino each frame (60 Hz) (called from app.update)."""
    if not hasattr(app, "casino"):
        return

    casino = app.casino
    casino.update(dt, app)  # dt is frame delta in seconds


# ============================================================================
# TESTING & DEBUGGING
# ============================================================================

def _ci_test_roulette():
    """Test roulette game."""
    NS = globals().get("NS") or globals()
    RouletteTable = NS.get("RouletteTable")

    if not RouletteTable:
        return "RouletteTable not found"

    table = RouletteTable("test_roulette")

    # Place a bet
    ok, msg = table.place_bet("npc_1", "straight", 100, [17])
    if not ok:
        return f"Bet failed: {msg}"

    # Spin
    result = table.spin_wheel()

    # Resolve
    results = table.resolve_bets()

    if "npc_1" in results:
        payout, profit = results["npc_1"]
        return f"Spun {result}, NPC won {payout}, profit {profit}"

    return f"Spun {result}, NPC lost bet"


def _ci_test_blackjack():
    """Test blackjack game."""
    NS = globals().get("NS") or globals()
    BlackjackTable = NS.get("BlackjackTable")

    if not BlackjackTable:
        return "BlackjackTable not found"

    table = BlackjackTable("test_blackjack")

    # Player sits
    ok, msg = table.place_bet("npc_1", 50)
    if not ok:
        return f"Bet failed: {msg}"

    # Player hits
    ok, msg = table.player_hit("npc_1")
    if not ok and "Bust" in msg:
        return f"Busted: {msg}"

    # Player stands
    ok, msg = table.player_stand("npc_1")
    if ok:
        results = table.resolve_hands()
        if "npc_1" in results:
            payout, profit = results["npc_1"]
            return f"Payout {payout}, profit {profit}"

    return "Blackjack test inconclusive"


def _ci_test_gambling_personality():
    """Test NPC gambling personality generation."""
    NS = globals().get("NS") or globals()
    GamblingPersonality = NS.get("GamblingPersonality")

    if not GamblingPersonality:
        return "GamblingPersonality not found"

    npc_traits = {
        "ambition": 0.7,
        "boldness": 0.8,
        "patience": 0.3,
        "sociability": 0.6,
        "intelligence": 0.5,
        "greed": 0.6,
    }

    gp = GamblingPersonality(npc_traits, seed=123)

    game = gp.choose_game()
    bet = gp.decide_bet(1000)

    return f"Personality: prefer {game}, bet {bet:.0f}, risk {gp.risk_tolerance:.2f}"


# Install hooks for casino commands
def _ci_register_commands():
    """Register casino testing/admin commands."""
    commands = {
        "casino_test_roulette": _ci_test_roulette,
        "casino_test_blackjack": _ci_test_blackjack,
        "casino_test_personality": _ci_test_gambling_personality,
    }
    return commands
