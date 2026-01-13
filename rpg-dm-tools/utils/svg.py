"""SVG map rendering for the RPG DM Tools."""

from typing import Dict, List, Optional, Tuple


# Room layout positions (x, y) on a grid
# Designed for the village map with vertical levels
ROOM_POSITIONS: Dict[str, Tuple[int, int, int]] = {
    # (grid_x, grid_y, level) - level 0 is ground, -1 is below
    "tavern": (2, 3, 0),
    "cellar": (2, 3, -1),  # Below tavern
    "street": (2, 2, 0),
    "market": (3, 2, 0),
    "blacksmith": (3, 1, 0),
    "temple": (1, 2, 0),
    "village_gate": (2, 1, 0),
    "forest_path": (2, 0, 0),
}

# SVG dimensions
CELL_SIZE = 100
ROOM_WIDTH = 80
ROOM_HEIGHT = 50
PADDING = 60


def get_room_center(room_id: str) -> Tuple[int, int]:
    """
    Get the center coordinates of a room in SVG space.

    Args:
        room_id: The room identifier

    Returns:
        (x, y) center coordinates
    """
    if room_id not in ROOM_POSITIONS:
        return (0, 0)

    grid_x, grid_y, level = ROOM_POSITIONS[room_id]

    # Convert grid position to SVG coordinates
    x = PADDING + grid_x * CELL_SIZE
    y = PADDING + grid_y * CELL_SIZE

    # Offset for underground rooms
    if level < 0:
        x += 15  # Slight offset to show it's below
        y += 15

    return (x, y)


def render_room(room_id: str, name: str, is_current: bool, level: int = 0) -> str:
    """
    Render a single room as SVG elements.

    Args:
        room_id: The room identifier
        name: Display name for the room
        is_current: Whether this is the current room
        level: Vertical level (0 = ground, -1 = below)

    Returns:
        SVG elements string for the room
    """
    x, y = get_room_center(room_id)

    # Colors
    fill = "#4a9eff" if is_current else "#e8e8e8"
    stroke = "#2563eb" if is_current else "#666"
    stroke_width = "3" if is_current else "2"
    text_color = "#ffffff" if is_current else "#333"

    # Dashed border for underground rooms
    stroke_dash = "5,3" if level < 0 else ""
    dash_attr = f' stroke-dasharray="{stroke_dash}"' if stroke_dash else ""

    # Format display name
    display_name = name.replace("_", " ").title()
    if len(display_name) > 12:
        display_name = display_name[:11] + "..."

    rect_x = x - ROOM_WIDTH // 2
    rect_y = y - ROOM_HEIGHT // 2

    return f'''  <rect x="{rect_x}" y="{rect_y}" width="{ROOM_WIDTH}" height="{ROOM_HEIGHT}"
        rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"{dash_attr}/>
  <text x="{x}" y="{y + 5}" text-anchor="middle" font-family="Arial, sans-serif"
        font-size="11" fill="{text_color}" font-weight="{'bold' if is_current else 'normal'}">{display_name}</text>'''


def render_connection(from_room: str, to_room: str, direction: str) -> str:
    """
    Render a connection line between two rooms.

    Args:
        from_room: Source room ID
        to_room: Destination room ID
        direction: Direction of exit (north, south, up, down, etc.)

    Returns:
        SVG line element string
    """
    from_x, from_y = get_room_center(from_room)
    to_x, to_y = get_room_center(to_room)

    # Adjust line endpoints to room edges
    if direction == "north":
        from_y -= ROOM_HEIGHT // 2
        to_y += ROOM_HEIGHT // 2
    elif direction == "south":
        from_y += ROOM_HEIGHT // 2
        to_y -= ROOM_HEIGHT // 2
    elif direction == "east":
        from_x += ROOM_WIDTH // 2
        to_x -= ROOM_WIDTH // 2
    elif direction == "west":
        from_x -= ROOM_WIDTH // 2
        to_x += ROOM_WIDTH // 2
    elif direction in ("up", "down"):
        # Vertical connections use dashed lines with stair icon
        from_x += ROOM_WIDTH // 2 - 10
        to_x += ROOM_WIDTH // 2 - 10
        if direction == "down":
            from_y += ROOM_HEIGHT // 2
            to_y -= ROOM_HEIGHT // 2
        else:
            from_y -= ROOM_HEIGHT // 2
            to_y += ROOM_HEIGHT // 2

    # Use dashed line for vertical connections
    is_vertical = direction in ("up", "down")
    dash = ' stroke-dasharray="4,2"' if is_vertical else ""

    return f'  <line x1="{from_x}" y1="{from_y}" x2="{to_x}" y2="{to_y}" stroke="#888" stroke-width="2"{dash}/>'


def render_vertical_indicator(room_id: str, has_up: bool, has_down: bool) -> str:
    """
    Render up/down indicators for rooms with vertical exits.

    Args:
        room_id: The room identifier
        has_up: Whether room has an "up" exit
        has_down: Whether room has a "down" exit

    Returns:
        SVG elements for vertical indicators
    """
    if not has_up and not has_down:
        return ""

    x, y = get_room_center(room_id)
    elements = []

    # Position indicators at room edge
    ind_x = x + ROOM_WIDTH // 2 - 8

    if has_up:
        ind_y = y - ROOM_HEIGHT // 2 + 8
        elements.append(
            f'  <polygon points="{ind_x},{ind_y} {ind_x-5},{ind_y+8} {ind_x+5},{ind_y+8}" '
            f'fill="#666" stroke="none"/>'
        )

    if has_down:
        ind_y = y + ROOM_HEIGHT // 2 - 8
        elements.append(
            f'  <polygon points="{ind_x},{ind_y} {ind_x-5},{ind_y-8} {ind_x+5},{ind_y-8}" '
            f'fill="#666" stroke="none"/>'
        )

    return "\n".join(elements)


def render_map_svg(rooms: Dict[str, dict], current_room: str) -> str:
    """
    Render the full map as an SVG image.

    Creates a top-down view of the map with:
    - Rooms as rounded rectangles with labels
    - Current room highlighted in blue
    - Connection lines between rooms
    - Vertical level indicators for stairs/ladders

    Args:
        rooms: Dictionary of room data from the map file
        current_room: ID of the player's current room

    Returns:
        Complete SVG string
    """
    # Calculate SVG dimensions based on room positions
    max_x = max(pos[0] for pos in ROOM_POSITIONS.values()) + 1
    max_y = max(pos[1] for pos in ROOM_POSITIONS.values()) + 1

    width = PADDING * 2 + max_x * CELL_SIZE
    height = PADDING * 2 + max_y * CELL_SIZE

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '  <!-- Background -->',
        f'  <rect width="{width}" height="{height}" fill="#f5f5f5"/>',
        '',
        '  <!-- Connections -->',
    ]

    # Track which connections we've drawn to avoid duplicates
    drawn_connections = set()

    # Draw connections first (so they appear behind rooms)
    for room_id, room_data in rooms.items():
        if room_id not in ROOM_POSITIONS:
            continue

        exits = room_data.get("exits", {})
        for direction, target_room in exits.items():
            if target_room not in ROOM_POSITIONS:
                continue

            # Create a unique key for this connection (sorted to avoid duplicates)
            conn_key = tuple(sorted([room_id, target_room]))
            if conn_key in drawn_connections:
                continue
            drawn_connections.add(conn_key)

            svg_parts.append(render_connection(room_id, target_room, direction))

    svg_parts.append('')
    svg_parts.append('  <!-- Rooms -->')

    # Draw rooms
    for room_id, room_data in rooms.items():
        if room_id not in ROOM_POSITIONS:
            continue

        level = ROOM_POSITIONS[room_id][2]
        is_current = room_id == current_room
        svg_parts.append(render_room(room_id, room_id, is_current, level))

        # Add vertical indicators
        exits = room_data.get("exits", {})
        has_up = "up" in exits
        has_down = "down" in exits
        indicator = render_vertical_indicator(room_id, has_up, has_down)
        if indicator:
            svg_parts.append(indicator)

    svg_parts.append('')
    svg_parts.append('  <!-- Legend -->')
    svg_parts.append(f'  <text x="10" y="{height - 10}" font-family="Arial, sans-serif" '
                     f'font-size="10" fill="#666">Current location: {current_room.replace("_", " ").title()}</text>')

    svg_parts.append('</svg>')

    return "\n".join(svg_parts)
