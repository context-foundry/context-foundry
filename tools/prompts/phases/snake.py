"""
Snake entity with movement and growth mechanics.
Handles snake behavior, direction changes, and collision detection.
"""

from collections import deque
from typing import Optional

from constants import (
    GRID_WIDTH,
    GRID_HEIGHT,
    DIRECTION_UP,
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    OPPOSITE_DIRECTIONS,
    INITIAL_SNAKE_LENGTH,
    INITIAL_SNAKE_POSITION,
    INITIAL_DIRECTION,
    INPUT_BUFFER_SIZE,
)


class Snake:
    """
    Snake class managing the snake's body, movement, and collision.

    The snake is represented as a deque of grid positions, with the head
    at index 0. Movement is grid-based for classic snake behavior.
    """

    def __init__(
        self,
        start_position: tuple[int, int] = INITIAL_SNAKE_POSITION,
        initial_length: int = INITIAL_SNAKE_LENGTH,
        initial_direction: tuple[int, int] = INITIAL_DIRECTION
    ):
        """
        Initialize the snake.

        Args:
            start_position: Starting grid position for the head
            initial_length: Initial number of segments
            initial_direction: Initial movement direction
        """
        self.body: deque[tuple[int, int]] = deque()
        self.direction: tuple[int, int] = initial_direction
        self.next_direction: tuple[int, int] = initial_direction
        self.input_buffer: deque[tuple[int, int]] = deque(maxlen=INPUT_BUFFER_SIZE)
        self.growing: bool = False

        # Initialize snake body
        self._initialize_body(start_position, initial_length, initial_direction)

    def _initialize_body(
        self,
        head_position: tuple[int, int],
        length: int,
        direction: tuple[int, int]
    ) -> None:
        """
        Initialize the snake body segments.

        Args:
            head_position: Position of the head
            length: Number of segments
            direction: Direction the snake is facing (body extends opposite)
        """
        self.body.clear()

        # Calculate opposite direction to place body behind head
        dx, dy = direction
        for i in range(length):
            segment_x = head_position[0] - (dx * i)
            segment_y = head_position[1] - (dy * i)
            self.body.append((segment_x, segment_y))

    @property
    def head(self) -> tuple[int, int]:
        """Get the position of the snake's head."""
        return self.body[0]

    @property
    def tail(self) -> tuple[int, int]:
        """Get the position of the snake's tail."""
        return self.body[-1]

    @property
    def length(self) -> int:
        """Get the current length of the snake."""
        return len(self.body)

    def change_direction(self, new_direction: tuple[int, int]) -> bool:
        """
        Request a direction change (buffered input).

        Direction changes are validated to prevent reverse moves.
        Uses input buffering to handle rapid key presses.

        Args:
            new_direction: The requested new direction

        Returns:
            True if direction change was queued, False if invalid
        """
        # Validate direction
        if new_direction not in (DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT):
            return False

        # Get the direction to compare against (either last buffered or current)
        compare_direction = self.input_buffer[-1] if self.input_buffer else self.direction

        # Prevent reverse direction
        if new_direction == OPPOSITE_DIRECTIONS.get(compare_direction):
            return False

        # Don't buffer same direction
        if new_direction == compare_direction:
            return False

        # Add to input buffer
        self.input_buffer.append(new_direction)
        return True

    def move(self) -> tuple[int, int]:
        """
        Move the snake one step in the current direction.

        Processes input buffer and updates position.

        Returns:
            The new head position after moving
        """
        # Process input buffer
        if self.input_buffer:
            self.direction = self.input_buffer.popleft()

        # Calculate new head position
        head_x, head_y = self.head
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Add new head
        self.body.appendleft(new_head)

        # Remove tail unless growing
        if self.growing:
            self.growing = False
        else:
            self.body.pop()

        return new_head

    def grow(self) -> None:
        """
        Mark the snake to grow by one segment on next move.
        """
        self.growing = True

    def check_wall_collision(self) -> bool:
        """
        Check if the snake's head has collided with a wall.

        Returns:
            True if collision detected, False otherwise
        """
        head_x, head_y = self.head
        return not (0 <= head_x < GRID_WIDTH and 0 <= head_y < GRID_HEIGHT)

    def check_self_collision(self) -> bool:
        """
        Check if the snake's head has collided with its body.

        Returns:
            True if collision detected, False otherwise
        """
        # Head can't collide with itself, so check against body (excluding head)
        return self.head in list(self.body)[1:]

    def check_collision(self) -> bool:
        """
        Check for any collision (wall or self).

        Returns:
            True if any collision detected, False otherwise
        """
        return self.check_wall_collision() or self.check_self_collision()

    def check_position_collision(self, position: tuple[int, int]) -> bool:
        """
        Check if a position collides with the snake's body.

        Args:
            position: Grid position to check

        Returns:
            True if position is occupied by snake, False otherwise
        """
        return position in self.body

    def get_body_positions(self) -> list[tuple[int, int]]:
        """
        Get all body positions as a list.

        Returns:
            List of grid positions for all snake segments
        """
        return list(self.body)

    def reset(
        self,
        start_position: tuple[int, int] = INITIAL_SNAKE_POSITION,
        initial_length: int = INITIAL_SNAKE_LENGTH,
        initial_direction: tuple[int, int] = INITIAL_DIRECTION
    ) -> None:
        """
        Reset the snake to initial state.

        Args:
            start_position: Starting grid position for the head
            initial_length: Initial number of segments
            initial_direction: Initial movement direction
        """
        self.direction = initial_direction
        self.next_direction = initial_direction
        self.input_buffer.clear()
        self.growing = False
        self._initialize_body(start_position, initial_length, initial_direction)
