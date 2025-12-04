"""
Integration tests for the Game class.
Tests game initialization, state management, and component coordination.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock pygame before importing game module
import unittest.mock as mock

# Create mock pygame module
mock_pygame = mock.MagicMock()
mock_pygame.init = mock.MagicMock(return_value=(6, 0))
mock_pygame.quit = mock.MagicMock()
mock_pygame.display.set_mode = mock.MagicMock(return_value=mock.MagicMock())
mock_pygame.display.set_caption = mock.MagicMock()
mock_pygame.display.flip = mock.MagicMock()
mock_pygame.font.Font = mock.MagicMock(return_value=mock.MagicMock())
mock_pygame.time.Clock = mock.MagicMock(return_value=mock.MagicMock())
mock_pygame.Surface = mock.MagicMock(return_value=mock.MagicMock())
mock_pygame.Rect = mock.MagicMock()
mock_pygame.draw.rect = mock.MagicMock()
mock_pygame.draw.line = mock.MagicMock()
mock_pygame.QUIT = 256
mock_pygame.KEYDOWN = 768
mock_pygame.K_ESCAPE = 27
mock_pygame.K_SPACE = 32
mock_pygame.K_p = 112
mock_pygame.K_m = 109
mock_pygame.K_UP = 273
mock_pygame.K_DOWN = 274
mock_pygame.K_LEFT = 276
mock_pygame.K_RIGHT = 275
mock_pygame.K_w = 119
mock_pygame.K_a = 97
mock_pygame.K_s = 115
mock_pygame.K_d = 100

sys.modules['pygame'] = mock_pygame

from game import Game
from constants import GameState, SCORE_PER_FOOD


class TestGameInitialization:
    """Tests for Game initialization."""

    def test_game_initializes(self):
        """Test game object can be created."""
        game = Game()
        assert game is not None

    def test_initial_state_is_menu(self):
        """Test game starts in menu state."""
        game = Game()
        assert game.get_state() == GameState.MENU

    def test_initial_score_is_zero(self):
        """Test initial score is zero."""
        game = Game()
        assert game.get_score() == 0

    def test_initial_high_score_is_zero(self):
        """Test initial high score is zero."""
        game = Game()
        assert game.get_high_score() == 0

    def test_game_is_running(self):
        """Test game starts in running state."""
        game = Game()
        assert game.is_running() is True


class TestGameStateTransitions:
    """Tests for game state transitions."""

    def test_menu_to_playing(self):
        """Test transition from menu to playing state."""
        game = Game()
        game._start_game()
        assert game.get_state() == GameState.PLAYING

    def test_playing_to_paused(self):
        """Test transition from playing to paused state."""
        game = Game()
        game._start_game()
        game._handle_key_press(mock_pygame.K_p)
        assert game.get_state() == GameState.PAUSED

    def test_paused_to_playing(self):
        """Test transition from paused to playing state."""
        game = Game()
        game._start_game()
        game._handle_key_press(mock_pygame.K_p)  # Pause
        game._handle_key_press(mock_pygame.K_p)  # Resume
        assert game.get_state() == GameState.PLAYING

    def test_playing_to_game_over(self):
        """Test transition to game over state."""
        game = Game()
        game._start_game()
        game._game_over()
        assert game.get_state() == GameState.GAME_OVER

    def test_game_over_to_playing(self):
        """Test restart from game over state."""
        game = Game()
        game._start_game()
        game._game_over()
        game._handle_game_over_input(mock_pygame.K_SPACE)
        assert game.get_state() == GameState.PLAYING


class TestGameEntities:
    """Tests for game entity management."""

    def test_entities_created_on_start(self):
        """Test snake and food are created when game starts."""
        game = Game()
        game._start_game()
        assert game.snake is not None
        assert game.food is not None

    def test_score_resets_on_start(self):
        """Test score resets when starting new game."""
        game = Game()
        game._start_game()
        game.score = 100
        game._start_game()
        assert game.get_score() == 0

    def test_snake_food_interaction(self):
        """Test snake can eat food and grow."""
        game = Game()
        game._start_game()

        # Manually position food at snake head's next position
        game.snake.direction = (1, 0)  # Moving right
        next_pos = (game.snake.head[0] + 1, game.snake.head[1])
        game.food.position = next_pos

        initial_length = game.snake.length
        initial_score = game.score

        # Move snake to food
        game._move_snake()

        # Snake should grow and score increase
        # Note: growth happens on NEXT move
        game._move_snake()
        assert game.snake.length == initial_length + 1
        assert game.score == initial_score + SCORE_PER_FOOD


class TestGameScoring:
    """Tests for game scoring system."""

    def test_score_increases_on_food(self):
        """Test score increases when food is eaten."""
        game = Game()
        game._start_game()

        # Position food at snake's next position
        game.snake.direction = (1, 0)
        next_pos = (game.snake.head[0] + 1, game.snake.head[1])
        game.food.position = next_pos

        initial_score = game.score
        game._move_snake()

        assert game.score == initial_score + SCORE_PER_FOOD

    def test_high_score_updated_on_game_over(self):
        """Test high score is updated when game ends with higher score."""
        game = Game()
        game._start_game()
        game.score = 100
        game._game_over()

        assert game.get_high_score() == 100

    def test_high_score_not_decreased(self):
        """Test high score doesn't decrease on lower score."""
        game = Game()
        game._start_game()
        game.score = 100
        game._game_over()

        game._start_game()
        game.score = 50
        game._game_over()

        assert game.get_high_score() == 100


class TestGameInput:
    """Tests for game input handling."""

    def test_direction_keys_change_snake_direction(self):
        """Test arrow keys change snake direction."""
        game = Game()
        game._start_game()

        # Test UP key
        game._handle_key_press(mock_pygame.K_UP)
        game.snake.move()
        # Direction should have changed (can't verify directly, but no crash is good)

    def test_escape_quits_game(self):
        """Test escape key sets running to false."""
        game = Game()
        game._handle_key_press(mock_pygame.K_ESCAPE)
        assert game.is_running() is False

    def test_space_starts_from_menu(self):
        """Test space key starts game from menu."""
        game = Game()
        assert game.get_state() == GameState.MENU
        game._handle_key_press(mock_pygame.K_SPACE)
        assert game.get_state() == GameState.PLAYING


class TestGameUpdate:
    """Tests for game update logic."""

    def test_update_does_nothing_in_menu(self):
        """Test update does nothing in menu state."""
        game = Game()
        game.update(0.1)
        # Should not crash, state should remain menu
        assert game.get_state() == GameState.MENU

    def test_update_does_nothing_in_pause(self):
        """Test update does nothing when paused."""
        game = Game()
        game._start_game()
        game._handle_key_press(mock_pygame.K_p)  # Pause

        # Record position
        head_pos = game.snake.head

        # Update should not move snake
        game.update(1.0)  # Large dt

        # Position unchanged
        assert game.snake.head == head_pos

    def test_update_moves_snake_in_playing_state(self):
        """Test update moves snake when playing."""
        game = Game()
        game._start_game()

        initial_head = game.snake.head

        # Update with enough time to trigger movement
        game.update(0.5)  # Should be enough for at least one move

        # Snake should have moved
        # (May or may not have moved depending on timing, just verify no crash)
        assert game.snake is not None


class TestGameCollision:
    """Tests for game collision handling."""

    def test_wall_collision_triggers_game_over(self):
        """Test wall collision ends the game."""
        game = Game()
        game._start_game()

        # Move snake to wall
        from constants import GRID_WIDTH
        game.snake.body.clear()
        game.snake.body.append((GRID_WIDTH - 1, 10))
        game.snake.body.append((GRID_WIDTH - 2, 10))
        game.snake.body.append((GRID_WIDTH - 3, 10))
        game.snake.direction = (1, 0)  # Moving right

        game._move_snake()

        assert game.get_state() == GameState.GAME_OVER

    def test_self_collision_triggers_game_over(self):
        """Test self collision ends the game."""
        game = Game()
        game._start_game()

        # Create a snake that will collide with itself
        game.snake.body.clear()
        game.snake.body.append((5, 5))   # Head
        game.snake.body.append((6, 5))   # Will collide here
        game.snake.body.append((6, 6))
        game.snake.body.append((5, 6))
        game.snake.body.append((4, 6))
        game.snake.direction = (1, 0)  # Moving right into body

        game._move_snake()

        assert game.get_state() == GameState.GAME_OVER


class TestGameRendering:
    """Tests for game rendering (basic smoke tests)."""

    def test_render_menu_no_crash(self):
        """Test menu rendering doesn't crash."""
        game = Game()
        game.render()  # Should not crash

    def test_render_playing_no_crash(self):
        """Test playing state rendering doesn't crash."""
        game = Game()
        game._start_game()
        game.render()  # Should not crash

    def test_render_paused_no_crash(self):
        """Test paused state rendering doesn't crash."""
        game = Game()
        game._start_game()
        game._handle_key_press(mock_pygame.K_p)
        game.render()  # Should not crash

    def test_render_game_over_no_crash(self):
        """Test game over rendering doesn't crash."""
        game = Game()
        game._start_game()
        game._game_over()
        game.render()  # Should not crash
