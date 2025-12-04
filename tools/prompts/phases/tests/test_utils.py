"""
Unit tests for utility functions.
Tests grid/pixel conversion and position validation helpers.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import (
    grid_to_pixel,
    pixel_to_grid,
    validate_position,
    get_grid_rect,
    clamp_to_grid,
    wrap_position,
    manhattan_distance,
)
from constants import GRID_SIZE, GRID_WIDTH, GRID_HEIGHT


class TestGridToPixel:
    """Tests for grid_to_pixel conversion."""

    def test_origin_conversion(self):
        """Test conversion at origin."""
        assert grid_to_pixel(0, 0) == (0, 0)

    def test_positive_grid_position(self):
        """Test conversion of positive grid position."""
        result = grid_to_pixel(5, 10)
        assert result == (5 * GRID_SIZE, 10 * GRID_SIZE)

    def test_max_grid_position(self):
        """Test conversion at maximum grid position."""
        result = grid_to_pixel(GRID_WIDTH - 1, GRID_HEIGHT - 1)
        expected = ((GRID_WIDTH - 1) * GRID_SIZE, (GRID_HEIGHT - 1) * GRID_SIZE)
        assert result == expected


class TestPixelToGrid:
    """Tests for pixel_to_grid conversion."""

    def test_origin_conversion(self):
        """Test conversion at origin."""
        assert pixel_to_grid(0, 0) == (0, 0)

    def test_exact_grid_boundary(self):
        """Test conversion at exact grid boundary."""
        result = pixel_to_grid(GRID_SIZE, GRID_SIZE)
        assert result == (1, 1)

    def test_within_cell(self):
        """Test conversion within a grid cell."""
        # Any pixel within a cell should map to same grid position
        for offset in range(GRID_SIZE):
            result = pixel_to_grid(GRID_SIZE + offset, GRID_SIZE + offset)
            assert result == (1, 1)

    def test_round_trip(self):
        """Test grid -> pixel -> grid round trip."""
        original = (5, 10)
        pixels = grid_to_pixel(*original)
        result = pixel_to_grid(*pixels)
        assert result == original


class TestValidatePosition:
    """Tests for validate_position function."""

    def test_valid_origin(self):
        """Test origin is valid."""
        assert validate_position(0, 0) is True

    def test_valid_center(self):
        """Test center position is valid."""
        assert validate_position(GRID_WIDTH // 2, GRID_HEIGHT // 2) is True

    def test_valid_max_position(self):
        """Test maximum valid position."""
        assert validate_position(GRID_WIDTH - 1, GRID_HEIGHT - 1) is True

    def test_invalid_negative_x(self):
        """Test negative x is invalid."""
        assert validate_position(-1, 5) is False

    def test_invalid_negative_y(self):
        """Test negative y is invalid."""
        assert validate_position(5, -1) is False

    def test_invalid_x_too_large(self):
        """Test x >= GRID_WIDTH is invalid."""
        assert validate_position(GRID_WIDTH, 5) is False

    def test_invalid_y_too_large(self):
        """Test y >= GRID_HEIGHT is invalid."""
        assert validate_position(5, GRID_HEIGHT) is False


class TestGetGridRect:
    """Tests for get_grid_rect function."""

    def test_rect_at_origin(self):
        """Test rect at origin."""
        result = get_grid_rect(0, 0)
        assert result == (0, 0, GRID_SIZE, GRID_SIZE)

    def test_rect_at_position(self):
        """Test rect at arbitrary position."""
        result = get_grid_rect(5, 10)
        expected = (5 * GRID_SIZE, 10 * GRID_SIZE, GRID_SIZE, GRID_SIZE)
        assert result == expected


class TestClampToGrid:
    """Tests for clamp_to_grid function."""

    def test_value_within_range(self):
        """Test value within valid range."""
        assert clamp_to_grid(5, 10) == 5

    def test_value_at_zero(self):
        """Test value at zero."""
        assert clamp_to_grid(0, 10) == 0

    def test_value_at_max_minus_one(self):
        """Test value at max - 1."""
        assert clamp_to_grid(9, 10) == 9

    def test_negative_value(self):
        """Test negative value is clamped to 0."""
        assert clamp_to_grid(-5, 10) == 0

    def test_value_exceeds_max(self):
        """Test value exceeding max is clamped."""
        assert clamp_to_grid(15, 10) == 9

    def test_value_at_max(self):
        """Test value at max is clamped to max - 1."""
        assert clamp_to_grid(10, 10) == 9


class TestWrapPosition:
    """Tests for wrap_position function."""

    def test_position_within_bounds(self):
        """Test position within bounds is unchanged."""
        result = wrap_position(5, 10)
        assert result == (5, 10)

    def test_wrap_x_positive(self):
        """Test x wraps when exceeding width."""
        result = wrap_position(GRID_WIDTH, 5)
        assert result == (0, 5)

    def test_wrap_y_positive(self):
        """Test y wraps when exceeding height."""
        result = wrap_position(5, GRID_HEIGHT)
        assert result == (5, 0)

    def test_wrap_x_negative(self):
        """Test negative x wraps around."""
        result = wrap_position(-1, 5)
        assert result == (GRID_WIDTH - 1, 5)

    def test_wrap_y_negative(self):
        """Test negative y wraps around."""
        result = wrap_position(5, -1)
        assert result == (5, GRID_HEIGHT - 1)

    def test_wrap_both_coordinates(self):
        """Test wrapping both coordinates."""
        result = wrap_position(GRID_WIDTH + 2, GRID_HEIGHT + 3)
        assert result == (2, 3)


class TestManhattanDistance:
    """Tests for manhattan_distance function."""

    def test_same_position(self):
        """Test distance to same position is 0."""
        assert manhattan_distance((5, 5), (5, 5)) == 0

    def test_horizontal_distance(self):
        """Test horizontal distance."""
        assert manhattan_distance((0, 5), (10, 5)) == 10

    def test_vertical_distance(self):
        """Test vertical distance."""
        assert manhattan_distance((5, 0), (5, 10)) == 10

    def test_diagonal_distance(self):
        """Test diagonal distance."""
        assert manhattan_distance((0, 0), (3, 4)) == 7

    def test_negative_coordinates(self):
        """Test with position differences (absolute values)."""
        assert manhattan_distance((10, 10), (5, 3)) == 12

    def test_origin_to_point(self):
        """Test distance from origin."""
        assert manhattan_distance((0, 0), (5, 5)) == 10
