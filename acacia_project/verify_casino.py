#!/usr/bin/env python3
"""
Verify casino modules load and integrate properly without full tkinter dependency.
"""

import sys
import os
import importlib.util

def load_module(name, path):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def verify_casino_integration():
    """Verify casino modules load and contain expected classes/functions."""
    print("=" * 60)
    print("CASINO INTEGRATION VERIFICATION")
    print("=" * 60)

    # Load casino modules
    print("\n1. Loading casino modules...")

    base_path = os.path.dirname(os.path.abspath(__file__))
    m55_path = os.path.join(base_path, "acacia/m55_casino.py")
    m56_path = os.path.join(base_path, "acacia/m56_casino_integration.py")

    m55 = load_module("m55_casino", m55_path)
    print("   ✓ m55_casino loaded")

    m56 = load_module("m56_casino_integration", m56_path)
    print("   ✓ m56_casino_integration loaded")

    # Verify core classes exist
    print("\n2. Verifying core classes...")

    classes = [
        "CasinoDistrict",
        "CasinoArea",
        "CasinoVisit",
        "RouletteWheel",
        "RouletteTable",
        "BlackjackTable",
        "BlackjackHand",
        "SlotMachine",
        "PokerTable",
        "PokerHand",
        "Dealer",
        "GamblingPersonality",
    ]

    for cls_name in classes:
        if hasattr(m55, cls_name):
            print(f"   ✓ {cls_name}")
        else:
            print(f"   ✗ {cls_name} NOT FOUND")
            return False

    # Verify integration functions
    print("\n3. Verifying integration functions...")

    functions = [
        "_ci_npc_should_gamble",
        "_ci_event_jackpot_won",
        "_ci_event_big_loss",
        "_ci_continuity_save",
        "_ci_continuity_load",
        "_ci_continuity_advance",
    ]

    for func_name in functions:
        if hasattr(m56, func_name):
            print(f"   ✓ {func_name}")
        else:
            print(f"   ✗ {func_name} NOT FOUND")
            return False

    # Verify casino actions are defined
    print("\n4. Verifying casino actions...")

    if hasattr(m56, "_CI_CASINO_ACTIONS"):
        actions = m56._CI_CASINO_ACTIONS
        print(f"   ✓ {len(actions)} casino actions defined:")
        for action in sorted(actions.keys()):
            print(f"      - {action}")
    else:
        print("   ✗ _CI_CASINO_ACTIONS not found")
        return False

    # Quick functionality test
    print("\n5. Quick functionality tests...")

    # Create a casino
    casino = m55.CasinoDistrict(seed=42, name="Test Casino")
    print(f"   ✓ Created casino: {casino.name}")
    print(f"      - {len(casino.areas)} areas")
    print(f"      - {len(casino.tables)} tables")
    print(f"      - Bankroll: ${casino.bankroll:.2f}")

    # Create a gambling personality
    traits = {"ambition": 0.7, "boldness": 0.6, "patience": 0.4, "intelligence": 0.6,
              "sociability": 0.5, "greed": 0.5}
    gp = m55.GamblingPersonality(traits, seed=123)
    print(f"   ✓ Created gambling personality")
    print(f"      - Risk tolerance: {gp.risk_tolerance:.2f}")
    print(f"      - Preferred game: {gp.choose_game()}")

    # Test roulette
    table = casino.tables["roulette_0"]
    ok, msg = table.place_bet("npc_test", "red_black", 100, ["red"])
    if ok:
        result = table.spin_wheel()
        payouts = table.resolve_bets()
        print(f"   ✓ Roulette spin: {result} (payout system working)")
    else:
        print(f"   ✗ Roulette bet failed: {msg}")
        return False

    # Test persistence
    data = casino.to_dict()
    casino2 = m55.CasinoDistrict.from_dict(data)
    if casino2.name == casino.name and casino2.bankroll == casino.bankroll:
        print(f"   ✓ Save/load persistence working")
    else:
        print(f"   ✗ Persistence broken")
        return False

    # Check manifest
    print("\n6. Checking manifest...")

    manifest_path = os.path.join(base_path, "acacia/_manifest.py")
    with open(manifest_path, 'r') as f:
        content = f.read()
        if "m55_casino" in content:
            print("   ✓ m55_casino in manifest")
        else:
            print("   ✗ m55_casino NOT in manifest")
            return False

        if "m56_casino_integration" in content:
            print("   ✓ m56_casino_integration in manifest")
        else:
            print("   ✗ m56_casino_integration NOT in manifest")
            return False

    print("\n" + "=" * 60)
    print("✓ ALL VERIFICATION CHECKS PASSED")
    print("=" * 60)
    print("\nCasino system is ready for integration with ACACIA!")
    print("\nNext steps:")
    print("  1. Run test_casino.py for comprehensive testing")
    print("  2. Add UI panels in m33_app.py or similar")
    print("  3. Add visual rendering for casino locations")
    print("  4. Integrate with NPC decision-making in m42_agency.py")
    print("  5. Test end-to-end with full application")

    return True

if __name__ == "__main__":
    success = verify_casino_integration()
    sys.exit(0 if success else 1)
