#!/usr/bin/env python3
"""
Integration tests for RPG DM Tools MCP Server.

This script tests all the server tools by:
1. Creating a test session
2. Listing all available tools
3. Calling each tool with sample input
4. Testing special update syntax
5. Testing movement validation
6. Verifying SVG output
7. Cleaning up test data

Usage:
    python test_server.py --port 8001
"""

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tools.dice import roll_dice
from tools.lore import lookup_geography, lookup_npc, lookup_creature, lookup_scenario
from tools.session import create_session, get_session_state
from tools.character import read_character, update_character
from tools.movement import get_current_map, move_character
from utils.state import get_session_path


# Test session ID
TEST_SESSION = "test_session_integration"
TEST_CHARACTER = "TestHero"


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(name: str, result: dict) -> None:
    """Print a formatted tool result."""
    print(f"\n--- {name} ---")
    print(json.dumps(result, indent=2))


def cleanup_test_session() -> None:
    """Remove test session directory if it exists."""
    session_path = get_session_path(TEST_SESSION)
    if session_path.exists():
        shutil.rmtree(session_path)
        print(f"Cleaned up test session: {TEST_SESSION}")


def test_dice_rolling() -> bool:
    """Test the dice rolling tool."""
    print_header("Testing Dice Rolling")

    test_cases = [
        "2d6+3",
        "1d20",
        "d20",
        "4d6-1",
        "3d6",
        "1d100",
    ]

    all_passed = True
    for notation in test_cases:
        result = roll_dice(notation)
        print_result(f"roll_dice('{notation}')", result)

        # Verify result structure
        if "error" in result:
            print(f"  ERROR: {result['error']}")
            all_passed = False
        else:
            if "rolls" not in result or "total" not in result:
                print("  ERROR: Missing required fields")
                all_passed = False
            elif len(result["rolls"]) == 0:
                print("  ERROR: No dice rolled")
                all_passed = False

    # Test invalid notation
    result = roll_dice("invalid")
    print_result("roll_dice('invalid') - should fail", result)
    if "error" not in result:
        print("  ERROR: Should have returned an error")
        all_passed = False

    return all_passed


def test_lore_lookups() -> bool:
    """Test the lore lookup tools."""
    print_header("Testing Lore Lookups")

    all_passed = True

    # Test geography
    result = lookup_geography("willowdale_village")
    print_result("lookup_geography('willowdale_village')", result)
    if not result.get("found"):
        print("  ERROR: Should have found willowdale_village")
        all_passed = False

    # Test geography with fuzzy match
    result = lookup_geography("willowdale")
    print_result("lookup_geography('willowdale') - fuzzy match", result)
    if result.get("found"):
        print("  Note: Found via partial match")
    elif "suggestions" not in result:
        print("  ERROR: Should have suggestions")
        all_passed = False

    # Test NPC lookup
    result = lookup_npc("marta_innkeeper")
    print_result("lookup_npc('marta_innkeeper')", result)
    if not result.get("found"):
        print("  ERROR: Should have found marta_innkeeper")
        all_passed = False

    # Test NPC by display name
    result = lookup_npc("Marta")
    print_result("lookup_npc('Marta') - by display name", result)
    if not result.get("found"):
        print("  ERROR: Should have found Marta by display name")
        all_passed = False

    # Test creature lookup
    result = lookup_creature("wolf")
    print_result("lookup_creature('wolf')", result)
    if not result.get("found"):
        print("  ERROR: Should have found wolf")
        all_passed = False

    # Test scenario lookup
    result = lookup_scenario("missing_merchant")
    print_result("lookup_scenario('missing_merchant')", result)
    if not result.get("found"):
        print("  ERROR: Should have found missing_merchant")
        all_passed = False

    # Test not found with suggestions
    result = lookup_npc("bob")
    print_result("lookup_npc('bob') - not found", result)
    if result.get("found"):
        print("  ERROR: Should not have found bob")
        all_passed = False

    return all_passed


def test_session_management() -> bool:
    """Test session creation and state."""
    print_header("Testing Session Management")

    all_passed = True

    # Clean up any existing test session
    cleanup_test_session()

    # Create a new session
    result = create_session(TEST_SESSION, TEST_CHARACTER)
    print_result(f"create_session('{TEST_SESSION}', '{TEST_CHARACTER}')", result)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    if result.get("session_id") != TEST_SESSION:
        print("  ERROR: Session ID mismatch")
        all_passed = False

    if result.get("character") != TEST_CHARACTER:
        print("  ERROR: Character name mismatch")
        all_passed = False

    # Try creating duplicate session
    result = create_session(TEST_SESSION, "AnotherHero")
    print_result("create_session (duplicate) - should fail", result)
    if "error" not in result:
        print("  ERROR: Should have failed for duplicate session")
        all_passed = False

    # Get session state
    result = get_session_state(TEST_SESSION)
    print_result(f"get_session_state('{TEST_SESSION}')", result)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        all_passed = False

    # Get non-existent session
    result = get_session_state("nonexistent_session")
    print_result("get_session_state('nonexistent_session') - should fail", result)
    if "error" not in result:
        print("  ERROR: Should have failed for non-existent session")
        all_passed = False

    return all_passed


def test_character_management() -> bool:
    """Test character reading and updates."""
    print_header("Testing Character Management")

    all_passed = True

    # Read character
    result = read_character(TEST_SESSION, TEST_CHARACTER)
    print_result(f"read_character('{TEST_SESSION}', '{TEST_CHARACTER}')", result)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    original_gold = result.get("gold", 0)
    original_inventory = result.get("inventory", []).copy()

    # Test nested update
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"stats.hp": 15})
    print_result("update_character - set stats.hp to 15", result)
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        all_passed = False
    elif result.get("character", {}).get("stats", {}).get("hp") != 15:
        print("  ERROR: HP not updated correctly")
        all_passed = False

    # Test inventory append
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"inventory+": "healing_potion"})
    print_result("update_character - append healing_potion to inventory", result)
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        all_passed = False
    elif "healing_potion" not in result.get("character", {}).get("inventory", []):
        print("  ERROR: Item not added to inventory")
        all_passed = False

    # Test inventory remove
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"inventory-": "rope"})
    print_result("update_character - remove rope from inventory", result)
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        all_passed = False
    elif "rope" in result.get("character", {}).get("inventory", []):
        print("  ERROR: Item not removed from inventory")
        all_passed = False

    # Test gold increment
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"gold": "+10"})
    print_result("update_character - add 10 gold", result)
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        all_passed = False
    elif result.get("character", {}).get("gold") != original_gold + 10:
        print("  ERROR: Gold not incremented correctly")
        all_passed = False

    # Test gold decrement
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"gold": "-5"})
    print_result("update_character - subtract 5 gold", result)
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        all_passed = False

    # Test insufficient gold (should fail)
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"gold": "-1000"})
    print_result("update_character - subtract 1000 gold (should fail)", result)
    if result.get("success"):
        print("  ERROR: Should have failed for insufficient gold")
        all_passed = False

    # Test HP exceeds max_hp (should cap at max)
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"stats.hp": 100})
    print_result("update_character - set HP to 100 (should cap at max_hp)", result)
    if result.get("success"):
        hp = result.get("character", {}).get("stats", {}).get("hp")
        max_hp = result.get("character", {}).get("stats", {}).get("max_hp")
        if hp > max_hp:
            print(f"  ERROR: HP ({hp}) exceeds max_hp ({max_hp})")
            all_passed = False

    # Test removing non-existent item (should fail)
    result = update_character(TEST_SESSION, TEST_CHARACTER, {"inventory-": "nonexistent_item"})
    print_result("update_character - remove nonexistent item (should fail)", result)
    if result.get("success"):
        print("  ERROR: Should have failed for non-existent item")
        all_passed = False

    return all_passed


def test_movement() -> bool:
    """Test map and movement tools."""
    print_header("Testing Map and Movement")

    all_passed = True

    # Get current map
    result = get_current_map(TEST_SESSION)
    print_result(f"get_current_map('{TEST_SESSION}')", result)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False

    current_room = result.get("current_room")
    exits = result.get("exits", {})
    svg = result.get("svg", "")

    print(f"  Current room: {current_room}")
    print(f"  Available exits: {list(exits.keys())}")

    # Verify SVG is valid XML
    try:
        ET.fromstring(svg)
        print("  SVG: Valid XML")
    except ET.ParseError as e:
        print(f"  ERROR: Invalid SVG XML: {e}")
        all_passed = False

    # Move to a valid direction
    if exits:
        direction = list(exits.keys())[0]
        target = exits[direction]
        result = move_character(TEST_SESSION, direction)
        print_result(f"move_character('{TEST_SESSION}', '{direction}')", result)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            all_passed = False
        elif result.get("current_room") != target:
            print(f"  ERROR: Expected to be in {target}, but in {result.get('current_room')}")
            all_passed = False

        # Verify SVG updated
        new_svg = result.get("svg", "")
        try:
            ET.fromstring(new_svg)
            print("  Updated SVG: Valid XML")
        except ET.ParseError as e:
            print(f"  ERROR: Invalid SVG XML after move: {e}")
            all_passed = False

    # Try invalid direction
    result = move_character(TEST_SESSION, "invalid_direction")
    print_result("move_character - invalid direction (should fail)", result)
    if result.get("success") != False:
        if "error" not in result:
            print("  ERROR: Should have failed for invalid direction")
            all_passed = False
    if "valid_exits" not in result:
        print("  Note: Should include valid_exits in error response")

    return all_passed


def test_tools_list() -> None:
    """Print information about available tools (simulated tools/list)."""
    print_header("Available Tools (Schema)")

    tools = [
        {
            "name": "roll_dice",
            "description": "Roll dice using standard dice notation (e.g., '2d6+3', 'd20')",
            "parameters": {"notation": "string - dice notation"},
        },
        {
            "name": "lookup_geography",
            "description": "Look up geographic region information",
            "parameters": {"region": "string - region name"},
        },
        {
            "name": "lookup_npc",
            "description": "Look up NPC information",
            "parameters": {"name": "string - NPC name"},
        },
        {
            "name": "lookup_creature",
            "description": "Look up creature stats and abilities",
            "parameters": {"creature_type": "string - creature type"},
        },
        {
            "name": "lookup_scenario",
            "description": "Look up adventure scenario details",
            "parameters": {"scenario_id": "string - scenario ID"},
        },
        {
            "name": "create_session",
            "description": "Create a new game session",
            "parameters": {
                "session_id": "string - unique session ID",
                "character_name": "string - character name",
            },
        },
        {
            "name": "get_session_state",
            "description": "Get current session state",
            "parameters": {"session_id": "string - session ID"},
        },
        {
            "name": "read_character",
            "description": "Read character sheet",
            "parameters": {
                "session_id": "string - session ID",
                "character_name": "string - character name",
            },
        },
        {
            "name": "update_character",
            "description": "Update character sheet with special syntax support",
            "parameters": {
                "session_id": "string - session ID",
                "character_name": "string - character name",
                "updates": "object - updates to apply",
            },
        },
        {
            "name": "get_current_map",
            "description": "Get current map with player position and SVG",
            "parameters": {"session_id": "string - session ID"},
        },
        {
            "name": "move_character",
            "description": "Move character to adjacent room",
            "parameters": {
                "session_id": "string - session ID",
                "direction": "string - direction to move",
            },
        },
    ]

    print("\nTools list (simulated MCP tools/list response):")
    print(json.dumps({"tools": tools}, indent=2))


def main():
    """Run all integration tests."""
    parser = argparse.ArgumentParser(description="Test RPG DM Tools MCP Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port (for documentation purposes, tests run directly)",
    )
    args = parser.parse_args()

    print(f"Running RPG DM Tools Integration Tests")
    print(f"(Note: Tests run directly against tool functions, not via HTTP on port {args.port})")

    results = {}

    try:
        # Print tools list
        test_tools_list()

        # Run tests
        results["Dice Rolling"] = test_dice_rolling()
        results["Lore Lookups"] = test_lore_lookups()
        results["Session Management"] = test_session_management()
        results["Character Management"] = test_character_management()
        results["Movement"] = test_movement()

    finally:
        # Clean up
        print_header("Cleanup")
        cleanup_test_session()

    # Summary
    print_header("Test Results Summary")
    all_passed = True
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
