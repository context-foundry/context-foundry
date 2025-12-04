"""
Utility functions and helpers for the Snake game.
Provides common operations for grid/pixel conversion and position validation.
"""

from constants import GRID_SIZE, GRID_WIDTH, GRID_HEIGHT


def grid_to_pixel(grid_x: int, grid_y: int) -> tuple[int, int]:
    """
    Convert grid coordinates to pixel coordinates.

    Args:
        grid_x: X position in grid units
        grid_y: Y position in grid units

    Returns:
        Tuple of (pixel_x, pixel_y) representing top-left corner of the cell
    """
    return (grid_x * GRID_SIZE, grid_y * GRID_SIZE)


def pixel_to_grid(pixel_x: int, pixel_y: int) -> tuple[int, int]:
    """
    Convert pixel coordinates to grid coordinates.

    Args:
        pixel_x: X position in pixels
        pixel_y: Y position in pixels

    Returns:
        Tuple of (grid_x, grid_y)
    """
    return (pixel_x // GRID_SIZE, pixel_y // GRID_SIZE)


def validate_position(grid_x: int, grid_y: int) -> bool:
    """
    Check if a grid position is within the game boundaries.

    Args:
        grid_x: X position in grid units
        grid_y: Y position in grid units

    Returns:
        True if position is valid (within bounds), False otherwise
    """
    return 0 <= grid_x < GRID_WIDTH and 0 <= grid_y < GRID_HEIGHT


def get_grid_rect(grid_x: int, grid_y: int) -> tuple[int, int, int, int]:
    """
    Get the pixel rectangle for a grid cell.

    Args:
        grid_x: X position in grid units
        grid_y: Y position in grid units

    Returns:
        Tuple of (x, y, width, height) for pygame.Rect
    """
    pixel_x, pixel_y = grid_to_pixel(grid_x, grid_y)
    return (pixel_x, pixel_y, GRID_SIZE, GRID_SIZE)


def clamp_to_grid(value: int, max_value: int) -> int:
    """
    Clamp a value to valid grid range.

    Args:
        value: The value to clamp
        max_value: Maximum grid value (exclusive)

    Returns:
        Clamped value within [0, max_value)
    """
    return max(0, min(value, max_value - 1))


def wrap_position(grid_x: int, grid_y: int) -> tuple[int, int]:
    """
    Wrap a position around the grid edges (for potential wrap-around mode).

    Args:
        grid_x: X position in grid units
        grid_y: Y position in grid units

    Returns:
        Tuple of wrapped (grid_x, grid_y)
    """
    return (grid_x % GRID_WIDTH, grid_y % GRID_HEIGHT)


def manhattan_distance(pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
    """
    Calculate Manhattan distance between two grid positions.

    Args:
        pos1: First position (grid_x, grid_y)
        pos2: Second position (grid_x, grid_y)

    Returns:
        Manhattan distance as integer
    """
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
