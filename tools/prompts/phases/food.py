"""
Food entity with spawning and collision logic.
Handles food positioning and consumption mechanics.
"""

import random
from typing import Optional

from constants import GRID_WIDTH, GRID_HEIGHT


class Food:
    """
    Food class managing food spawning and collision detection.

    Food spawns at random positions on the grid, ensuring it doesn't
    overlap with the snake's body.
    """

    def __init__(self, avoid_positions: Optional[list[tuple[int, int]]] = None):
        """
        Initialize the food at a random position.

        Args:
            avoid_positions: List of positions to avoid when spawning
        """
        self.position: tuple[int, int] = (0, 0)
        self.spawn(avoid_positions or [])

    def spawn(self, avoid_positions: list[tuple[int, int]]) -> tuple[int, int]:
        """
        Spawn food at a random position that doesn't overlap with given positions.

        Args:
            avoid_positions: List of positions where food cannot spawn

        Returns:
            The new food position
        """
        # Get all available positions
        available_positions = self._get_available_positions(avoid_positions)

        if not available_positions:
            # If no positions available (snake fills entire grid),
            # spawn at origin as fallback
            self.position = (0, 0)
        else:
            self.position = random.choice(available_positions)

        return self.position

    def _get_available_positions(
        self,
        avoid_positions: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """
        Get all grid positions not occupied by given positions.

        Args:
            avoid_positions: Positions to exclude

        Returns:
            List of available positions
        """
        avoid_set = set(avoid_positions)
        available = []

        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                if (x, y) not in avoid_set:
                    available.append((x, y))

        return available

    def respawn(self, avoid_positions: list[tuple[int, int]]) -> tuple[int, int]:
        """
        Respawn food at a new random position.

        Alias for spawn() for semantic clarity when food is consumed.

        Args:
            avoid_positions: List of positions where food cannot spawn

        Returns:
            The new food position
        """
        return self.spawn(avoid_positions)

    def check_collision(self, position: tuple[int, int]) -> bool:
        """
        Check if a position collides with the food.

        Args:
            position: Grid position to check

        Returns:
            True if position matches food position, False otherwise
        """
        return position == self.position

    def get_position(self) -> tuple[int, int]:
        """
        Get the current food position.

        Returns:
            Tuple of (grid_x, grid_y)
        """
        return self.position

    @staticmethod
    def is_valid_spawn_position(
        position: tuple[int, int],
        avoid_positions: list[tuple[int, int]]
    ) -> bool:
        """
        Check if a position is valid for food spawning.

        Args:
            position: Position to check
            avoid_positions: List of positions to avoid

        Returns:
            True if position is valid (not in avoid list and within bounds)
        """
        if position in avoid_positions:
            return False

        x, y = position
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            return False

        return True
