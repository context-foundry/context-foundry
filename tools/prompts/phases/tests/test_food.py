"""
Unit tests for the Food class.
Tests spawning logic, position validation, and collision detection.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from food import Food
from constants import GRID_WIDTH, GRID_HEIGHT


class TestFoodInitialization:
    """Tests for Food initialization."""

    def test_default_initialization(self):
        """Test food initializes at a valid position."""
        food = Food()
        x, y = food.get_position()
        assert 0 <= x < GRID_WIDTH
        assert 0 <= y < GRID_HEIGHT

    def test_initialization_avoids_positions(self):
        """Test food doesn't spawn on avoided positions."""
        avoid = [(5, 5), (5, 6), (5, 7)]
        food = Food(avoid_positions=avoid)
        assert food.get_position() not in avoid


class TestFoodSpawning:
    """Tests for Food spawning mechanics."""

    def test_spawn_returns_valid_position(self):
        """Test spawn returns a valid grid position."""
        food = Food()
        position = food.spawn([])
        x, y = position
        assert 0 <= x < GRID_WIDTH
        assert 0 <= y < GRID_HEIGHT

    def test_spawn_avoids_snake_body(self):
        """Test spawn avoids all snake body positions."""
        snake_positions = [(i, 10) for i in range(20)]
        food = Food()

        # Spawn multiple times to verify
        for _ in range(10):
            position = food.spawn(snake_positions)
            assert position not in snake_positions

    def test_spawn_position_is_stored(self):
        """Test spawn updates the food's stored position."""
        food = Food()
        new_position = food.spawn([])
        assert food.get_position() == new_position

    def test_respawn_alias_works(self):
        """Test respawn() works same as spawn()."""
        food = Food()
        snake_positions = [(i, 10) for i in range(10)]
        position = food.respawn(snake_positions)
        assert position not in snake_positions
        assert food.get_position() == position

    def test_spawn_with_many_avoided_positions(self):
        """Test spawn works when most positions are avoided."""
        # Create a list of most positions
        avoid = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT - 1):  # Leave last row available
                avoid.append((x, y))

        food = Food()
        position = food.spawn(avoid)
        assert position not in avoid

    def test_spawn_fallback_when_no_positions(self):
        """Test spawn has fallback when no positions available."""
        # Fill entire grid
        avoid = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                avoid.append((x, y))

        food = Food()
        # Should not crash, falls back to (0, 0)
        position = food.spawn(avoid)
        assert position == (0, 0)


class TestFoodCollision:
    """Tests for Food collision detection."""

    def test_collision_with_food_position(self):
        """Test collision returns True for food position."""
        food = Food()
        food.position = (5, 5)
        assert food.check_collision((5, 5)) is True

    def test_no_collision_different_position(self):
        """Test collision returns False for different position."""
        food = Food()
        food.position = (5, 5)
        assert food.check_collision((6, 5)) is False
        assert food.check_collision((5, 6)) is False

    def test_collision_at_origin(self):
        """Test collision works at origin."""
        food = Food()
        food.position = (0, 0)
        assert food.check_collision((0, 0)) is True

    def test_collision_at_edge(self):
        """Test collision works at grid edges."""
        food = Food()
        food.position = (GRID_WIDTH - 1, GRID_HEIGHT - 1)
        assert food.check_collision((GRID_WIDTH - 1, GRID_HEIGHT - 1)) is True


class TestFoodValidation:
    """Tests for Food position validation."""

    def test_valid_spawn_position_empty(self):
        """Test valid position when no avoided positions."""
        assert Food.is_valid_spawn_position((5, 5), []) is True

    def test_invalid_spawn_position_occupied(self):
        """Test invalid position when occupied."""
        avoid = [(5, 5)]
        assert Food.is_valid_spawn_position((5, 5), avoid) is False

    def test_invalid_spawn_position_out_of_bounds(self):
        """Test invalid position when out of bounds."""
        assert Food.is_valid_spawn_position((-1, 5), []) is False
        assert Food.is_valid_spawn_position((GRID_WIDTH, 5), []) is False
        assert Food.is_valid_spawn_position((5, -1), []) is False
        assert Food.is_valid_spawn_position((5, GRID_HEIGHT), []) is False

    def test_valid_spawn_position_at_edges(self):
        """Test valid positions at grid edges."""
        assert Food.is_valid_spawn_position((0, 0), []) is True
        assert Food.is_valid_spawn_position((GRID_WIDTH - 1, 0), []) is True
        assert Food.is_valid_spawn_position((0, GRID_HEIGHT - 1), []) is True
        assert Food.is_valid_spawn_position((GRID_WIDTH - 1, GRID_HEIGHT - 1), []) is True


class TestFoodRandomness:
    """Tests for Food spawning randomness."""

    def test_spawn_produces_varied_positions(self):
        """Test that spawn produces different positions over multiple calls."""
        food = Food()
        positions = set()

        # Spawn many times and collect positions
        for _ in range(100):
            pos = food.spawn([])
            positions.add(pos)

        # Should have spawned at multiple different positions
        # (statistically very unlikely to always spawn at same position)
        assert len(positions) > 1

    def test_spawn_distribution(self):
        """Test that spawn covers different areas of the grid."""
        food = Food()

        # Track which quadrants get food
        quadrants = {"top_left": False, "top_right": False,
                     "bottom_left": False, "bottom_right": False}

        for _ in range(200):
            x, y = food.spawn([])
            mid_x = GRID_WIDTH // 2
            mid_y = GRID_HEIGHT // 2

            if x < mid_x and y < mid_y:
                quadrants["top_left"] = True
            elif x >= mid_x and y < mid_y:
                quadrants["top_right"] = True
            elif x < mid_x and y >= mid_y:
                quadrants["bottom_left"] = True
            else:
                quadrants["bottom_right"] = True

        # Should have spawned in all quadrants
        assert all(quadrants.values())
