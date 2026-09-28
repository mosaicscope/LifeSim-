#!/usr/bin/env python3
"""
Casino system test suite for ACACIA M55/M56.

Tests:
  - Roulette wheel and betting
  - Blackjack game flow
  - Slot machine payouts
  - Poker table initialization
  - NPC gambling personalities
  - Save/load persistence
  - Integration points
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load casino modules directly (skip full acacia load which requires tkinter)
spec_m55 = __import__('importlib.util').util.spec_from_file_location(
    "m55_casino",
    os.path.join(os.path.dirname(__file__), "acacia/m55_casino.py")
)
m55_casino = __import__('importlib.util').util.module_from_spec(spec_m55)
spec_m55.loader.exec_module(m55_casino)

spec_m56 = __import__('importlib.util').util.spec_from_file_location(
    "m56_casino_integration",
    os.path.join(os.path.dirname(__file__), "acacia/m56_casino_integration.py")
)
m56_casino_integration = __import__('importlib.util').util.module_from_spec(spec_m56)
spec_m56.loader.exec_module(m56_casino_integration)


def test_roulette():
    """Test roulette wheel and betting."""
    print("\n=== ROULETTE TESTS ===")

    table = m55_casino.RouletteTable("test_roulette", bet_min=10, bet_max=1000)

    # Test bet placement
    ok, msg = table.place_bet("npc_1", "straight", 100, [17])
    print(f"✓ Place bet: {ok} ({msg})")
    assert ok, "Failed to place bet"

    # Test invalid bet
    ok, msg = table.place_bet("npc_2", "straight", 5, [5])
    print(f"✓ Invalid bet rejected: {not ok}")
    assert not ok, "Should reject under-limit bet"

    # Test spin and resolution
    result = table.spin_wheel()
    print(f"✓ Wheel spun: {result} (0-36)")
    assert 0 <= result <= 36, f"Invalid result: {result}"

    results = table.resolve_bets()
    print(f"✓ Bets resolved: {results}")

    print("✓ Roulette tests passed")


def test_blackjack():
    """Test blackjack game flow."""
    print("\n=== BLACKJACK TESTS ===")

    table = m55_casino.BlackjackTable("test_blackjack", bet_min=5, bet_max=500)

    # Place bet
    ok, msg = table.place_bet("npc_1", 50)
    print(f"✓ Placed bet: {ok}")
    assert ok, "Failed to place bet"

    # Check hand value
    hand = table.players["npc_1"]
    value = hand.value()
    print(f"✓ Hand value: {value}")
    assert 4 <= value <= 21, f"Invalid hand value: {value}"

    # Test hit
    ok, msg = table.player_hit("npc_1")
    new_value = hand.value()
    print(f"✓ After hit: {new_value} (bust={hand.bust()})")

    if not hand.bust():
        # Stand and resolve
        ok, msg = table.player_stand("npc_1")
        results = table.resolve_hands()
        if "npc_1" in results:
            payout, profit = results["npc_1"]
            print(f"✓ Resolved: payout={payout}, profit={profit}")

    print("✓ Blackjack tests passed")


def test_slots():
    """Test slot machine spins."""
    print("\n=== SLOTS TESTS ===")

    machine = m55_casino.SlotMachine("test_slots", seed=42)

    # Spin with various wagers
    for wager in [10, 50, 100]:
        reels, payout = machine.spin(wager)
        print(f"✓ Spin {wager}: {reels} -> payout {payout}")
        assert reels is not None, "Failed to spin"
        assert payout >= 0, "Invalid payout"

    print(f"✓ Machine totals: wagered={machine.total_wagered}, paid={machine.total_paid}")
    print("✓ Slots tests passed")


def test_poker():
    """Test poker table initialization."""
    print("\n=== POKER TESTS ===")

    table = m55_casino.PokerTable("test_poker", bet_min=25, bet_max=2000)

    # Player joins
    ok = table.join("npc_1", stack=500)
    print(f"✓ Player joined: {ok}")
    assert ok, "Failed to join table"

    # Check hand
    hand = table.players["npc_1"]
    print(f"✓ Hole cards: {hand.hole}")
    assert len(hand.hole) == 2, "Should have 2 hole cards"

    # Player leaves
    ok = table.leave("npc_1")
    print(f"✓ Player left: {ok}")
    assert ok, "Failed to leave table"

    print("✓ Poker tests passed")


def test_gambling_personality():
    """Test NPC gambling personality generation."""
    print("\n=== GAMBLING PERSONALITY TESTS ===")

    npc_traits = {
        "ambition": 0.7,
        "boldness": 0.8,
        "patience": 0.3,
        "sociability": 0.6,
        "intelligence": 0.5,
        "greed": 0.6,
    }

    gp = m55_casino.GamblingPersonality(npc_traits, seed=123)

    # Test trait derivation
    print(f"✓ Risk tolerance: {gp.risk_tolerance:.2f}")
    print(f"✓ Patience: {gp.patience:.2f}")
    print(f"✓ Greed: {gp.greed:.2f}")

    # Test game choice
    game = gp.choose_game()
    print(f"✓ Preferred game: {game}")
    assert game in ["roulette", "blackjack", "slots", "poker"], f"Invalid game: {game}"

    # Test bet decision
    bet = gp.decide_bet(1000)
    print(f"✓ Bet amount: {bet:.0f}")
    assert 10 <= bet <= 200, f"Bet out of range: {bet}"

    # Test continuation logic
    should_continue = gp.should_continue(500, won=0, lost=100, session_duration=30)
    print(f"✓ Should continue: {should_continue}")

    # Test to_dict
    data = gp.to_dict()
    print(f"✓ Serialized: {len(data)} fields")

    print("✓ Gambling personality tests passed")


def test_casino_district():
    """Test casino district initialization and operation."""
    print("\n=== CASINO DISTRICT TESTS ===")

    casino = m55_casino.CasinoDistrict(seed=42, name="Test Casino")

    # Check areas
    print(f"✓ Areas: {len(casino.areas)} locations")
    assert len(casino.areas) >= 5, "Should have at least 5 areas"

    # Check tables
    print(f"✓ Tables: {len(casino.tables)} tables")
    assert "roulette_0" in casino.tables, "Missing roulette table"
    assert "blackjack_0" in casino.tables, "Missing blackjack table"
    assert "poker_0" in casino.tables, "Missing poker table"

    # Check staff
    print(f"✓ Staff: {len(casino.dealers)} dealers")
    assert len(casino.dealers) > 0, "Should have dealers"

    # Check finances
    print(f"✓ Bankroll: {casino.bankroll}")
    print(f"✓ Jackpots: {casino.jackpots}")
    assert casino.bankroll > 0, "Casino should have bankroll"

    # Test NPC visit
    visit = casino.npc_enter("npc_1", 500)
    print(f"✓ NPC entered with bankroll: {visit.initial_bankroll}")
    assert "npc_1" in casino.npcs_present, "NPC not tracked"

    # Simulate some casino time
    casino.update(0.016, None)  # 60 Hz frame

    # Test NPC leave
    delta = casino.npc_leave("npc_1", visit)
    print(f"✓ NPC left, profit: {delta}")

    # Test event logging
    casino.log_event("bigwin", "npc_1", 1000, "roulette_0")
    print(f"✓ Event logged: {len(casino.events)} total")

    # Test serialization
    data = casino.to_dict()
    print(f"✓ Serialized: {len(data)} fields")
    assert data["name"] == "Test Casino", "Name mismatch"

    print("✓ Casino district tests passed")


def test_persistence():
    """Test save/load persistence."""
    print("\n=== PERSISTENCE TESTS ===")

    # Create and modify casino
    casino1 = m55_casino.CasinoDistrict(seed=42)
    casino1.revenue = 5000
    casino1.bankroll = 55000
    casino1.daily_visitors = 50

    # Serialize
    data = casino1.to_dict()
    print(f"✓ Serialized: revenue={data['revenue']}")

    # Deserialize
    casino2 = m55_casino.CasinoDistrict.from_dict(data)
    print(f"✓ Deserialized: revenue={casino2.revenue}")

    # Verify state preserved
    assert casino2.revenue == casino1.revenue, "Revenue not preserved"
    assert casino2.bankroll == casino1.bankroll, "Bankroll not preserved"
    assert casino2.daily_visitors == casino1.daily_visitors, "Visitors not preserved"

    print("✓ Persistence tests passed")


def test_integration():
    """Test integration with existing ACACIA systems."""
    print("\n=== INTEGRATION TESTS ===")

    # Test gambling personality generation
    npc_traits = {"ambition": 0.5, "boldness": 0.5, "patience": 0.5, "sociability": 0.5,
                  "intelligence": 0.5, "greed": 0.5}
    gp = m55_casino.GamblingPersonality(npc_traits, seed=1)
    print(f"✓ Created gambling personality")

    # Test should_gamble logic
    should_gamble = m56_casino_integration._ci_npc_should_gamble(
        None, gp, 1000, mood=0.5
    )
    print(f"✓ NPC should gamble: {should_gamble}")

    # Test casino actions
    print(f"✓ Casino actions defined: {len(m56_casino_integration._CI_CASINO_ACTIONS)} actions")

    # Test event functions
    event = m56_casino_integration._ci_event_jackpot_won(None, "npc_1", 5000, "roulette")
    print(f"✓ Jackpot event created: {event is None or 'jackpot' in str(event)}")

    print("✓ Integration tests passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("ACACIA CASINO SYSTEM TEST SUITE")
    print("=" * 60)

    tests = [
        test_roulette,
        test_blackjack,
        test_slots,
        test_poker,
        test_gambling_personality,
        test_casino_district,
        test_persistence,
        test_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
