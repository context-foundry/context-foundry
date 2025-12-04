"""
Game constants and configuration settings.
Centralized configuration for the Snake game.
"""

# Window settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "Snake Game"

# Grid settings
GRID_SIZE = 20  # Size of each grid cell in pixels
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE

# Frame rate
FPS = 60

# Snake movement speed (moves per second)
SNAKE_SPEED = 10

# Colors (RGB)
COLORS = {
    "background": (20, 20, 20),
    "snake_head": (0, 200, 0),
    "snake_body": (0, 150, 0),
    "food": (200, 0, 0),
    "text": (255, 255, 255),
    "grid_line": (40, 40, 40),
    "menu_bg": (0, 0, 0),
    "menu_text": (255, 255, 255),
    "score_text": (255, 255, 0),
    "game_over_text": (255, 0, 0),
}

# Directions (as grid offsets)
DIRECTION_UP = (0, -1)
DIRECTION_DOWN = (0, 1)
DIRECTION_LEFT = (-1, 0)
DIRECTION_RIGHT = (1, 0)

# Direction opposites (for preventing reverse moves)
OPPOSITE_DIRECTIONS = {
    DIRECTION_UP: DIRECTION_DOWN,
    DIRECTION_DOWN: DIRECTION_UP,
    DIRECTION_LEFT: DIRECTION_RIGHT,
    DIRECTION_RIGHT: DIRECTION_LEFT,
}

# Game states
class GameState:
    """Enumeration of possible game states."""
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"

# Initial snake settings
INITIAL_SNAKE_LENGTH = 3
INITIAL_SNAKE_POSITION = (GRID_WIDTH // 2, GRID_HEIGHT // 2)
INITIAL_DIRECTION = DIRECTION_RIGHT

# Scoring
SCORE_PER_FOOD = 10

# Input buffer settings
INPUT_BUFFER_SIZE = 2

# Font settings
FONT_SIZE_LARGE = 48
FONT_SIZE_MEDIUM = 36
FONT_SIZE_SMALL = 24
