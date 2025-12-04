"""
Unit tests for the Snake class.
Tests movement mechanics, direction changes, growth, and collision detection.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snake import Snake
from constants import (
    DIRECTION_UP,
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    GRID_WIDTH,
    GRID_HEIGHT,
    INITIAL_SNAKE_LENGTH,
)


class TestSnakeInitialization:
    """Tests for Snake initialization."""

    def test_default_initialization(self):
        """Test snake initializes with default values."""
        snake = Snake()
        assert snake.length == INITIAL_SNAKE_LENGTH
        assert snake.direction == DIRECTION_RIGHT

    def test_custom_position(self):
        """Test snake initializes at custom position."""
        position = (5, 5)
        snake = Snake(start_position=position)
        assert snake.head == position

    def test_custom_length(self):
        """Test snake initializes with custom length."""
        length = 5
        snake = Snake(initial_length=length)
        assert snake.length == length

    def test_custom_direction(self):
        """Test snake initializes with custom direction."""
        snake = Snake(initial_direction=DIRECTION_UP)
        assert snake.direction == DIRECTION_UP

    def test_body_alignment(self):
        """Test snake body is aligned behind head."""
        snake = Snake(start_position=(10, 10), initial_length=3, initial_direction=DIRECTION_RIGHT)
        positions = snake.get_body_positions()
        assert positions[0] == (10, 10)  # Head
        assert positions[1] == (9, 10)   # Body segment
        assert positions[2] == (8, 10)   # Tail


class TestSnakeMovement:
    """Tests for Snake movement mechanics."""

    def test_move_right(self):
        """Test snake moves right correctly."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_RIGHT)
        snake.move()
        assert snake.head == (11, 10)

    def test_move_left(self):
        """Test snake moves left correctly."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_LEFT)
        snake.move()
        assert snake.head == (9, 10)

    def test_move_up(self):
        """Test snake moves up correctly."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_UP)
        snake.move()
        assert snake.head == (10, 9)

    def test_move_down(self):
        """Test snake moves down correctly."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_DOWN)
        snake.move()
        assert snake.head == (10, 11)

    def test_length_maintained_after_move(self):
        """Test snake length stays constant when not growing."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        initial_length = snake.length
        snake.move()
        assert snake.length == initial_length


class TestSnakeDirectionChange:
    """Tests for Snake direction changes."""

    def test_valid_direction_change(self):
        """Test valid direction change is accepted."""
        snake = Snake(initial_direction=DIRECTION_RIGHT)
        result = snake.change_direction(DIRECTION_UP)
        assert result is True

    def test_reverse_direction_rejected(self):
        """Test reverse direction is rejected."""
        snake = Snake(initial_direction=DIRECTION_RIGHT)
        result = snake.change_direction(DIRECTION_LEFT)
        assert result is False

    def test_same_direction_rejected(self):
        """Test same direction is rejected."""
        snake = Snake(initial_direction=DIRECTION_RIGHT)
        result = snake.change_direction(DIRECTION_RIGHT)
        assert result is False

    def test_direction_change_applied_on_move(self):
        """Test buffered direction change is applied on move."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_RIGHT)
        snake.change_direction(DIRECTION_UP)
        snake.move()
        assert snake.head == (10, 9)

    def test_invalid_direction_rejected(self):
        """Test invalid direction tuple is rejected."""
        snake = Snake()
        result = snake.change_direction((2, 2))  # Invalid direction
        assert result is False

    def test_input_buffer_handles_rapid_changes(self):
        """Test input buffer handles rapid direction changes."""
        snake = Snake(start_position=(10, 10), initial_direction=DIRECTION_RIGHT)
        snake.change_direction(DIRECTION_UP)
        snake.change_direction(DIRECTION_LEFT)  # This should be buffered
        snake.move()  # Should go UP
        assert snake.head == (10, 9)
        snake.move()  # Should go LEFT
        assert snake.head == (9, 9)


class TestSnakeGrowth:
    """Tests for Snake growth mechanics."""

    def test_grow_increases_length(self):
        """Test grow() increases snake length on next move."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        initial_length = snake.length
        snake.grow()
        snake.move()
        assert snake.length == initial_length + 1

    def test_grow_only_once_per_call(self):
        """Test grow() only adds one segment per call."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        initial_length = snake.length
        snake.grow()
        snake.move()
        snake.move()  # Second move without grow()
        assert snake.length == initial_length + 1


class TestSnakeCollision:
    """Tests for Snake collision detection."""

    def test_wall_collision_right(self):
        """Test wall collision detection on right edge."""
        snake = Snake(start_position=(GRID_WIDTH - 1, 10), initial_direction=DIRECTION_RIGHT)
        snake.move()
        assert snake.check_wall_collision() is True

    def test_wall_collision_left(self):
        """Test wall collision detection on left edge."""
        snake = Snake(start_position=(0, 10), initial_direction=DIRECTION_LEFT)
        snake.move()
        assert snake.check_wall_collision() is True

    def test_wall_collision_top(self):
        """Test wall collision detection on top edge."""
        snake = Snake(start_position=(10, 0), initial_direction=DIRECTION_UP)
        snake.move()
        assert snake.check_wall_collision() is True

    def test_wall_collision_bottom(self):
        """Test wall collision detection on bottom edge."""
        snake = Snake(start_position=(10, GRID_HEIGHT - 1), initial_direction=DIRECTION_DOWN)
        snake.move()
        assert snake.check_wall_collision() is True

    def test_no_wall_collision_center(self):
        """Test no wall collision in center of grid."""
        snake = Snake(start_position=(10, 10))
        snake.move()
        assert snake.check_wall_collision() is False

    def test_self_collision(self):
        """Test self collision detection."""
        # Create long snake and make it collide with itself
        snake = Snake(start_position=(10, 10), initial_length=5, initial_direction=DIRECTION_RIGHT)
        snake.change_direction(DIRECTION_DOWN)
        snake.move()
        snake.change_direction(DIRECTION_LEFT)
        snake.move()
        snake.change_direction(DIRECTION_UP)
        snake.move()
        # Snake should now have collided with itself
        assert snake.check_self_collision() is True

    def test_no_self_collision_short_snake(self):
        """Test no self collision with short snake."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        snake.move()
        assert snake.check_self_collision() is False

    def test_check_collision_combined(self):
        """Test combined collision check."""
        snake = Snake(start_position=(GRID_WIDTH - 1, 10), initial_direction=DIRECTION_RIGHT)
        snake.move()
        assert snake.check_collision() is True

    def test_position_collision_check(self):
        """Test position collision with snake body."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        assert snake.check_position_collision((10, 10)) is True  # Head
        assert snake.check_position_collision((9, 10)) is True   # Body
        assert snake.check_position_collision((5, 5)) is False   # Empty


class TestSnakeReset:
    """Tests for Snake reset functionality."""

    def test_reset_restores_defaults(self):
        """Test reset() restores default state."""
        snake = Snake(start_position=(10, 10), initial_length=3)
        # Modify snake
        snake.move()
        snake.grow()
        snake.move()
        # Reset
        snake.reset()
        assert snake.length == INITIAL_SNAKE_LENGTH

    def test_reset_with_custom_values(self):
        """Test reset() with custom values."""
        snake = Snake()
        snake.reset(start_position=(5, 5), initial_length=5, initial_direction=DIRECTION_UP)
        assert snake.head == (5, 5)
        assert snake.length == 5
        assert snake.direction == DIRECTION_UP
