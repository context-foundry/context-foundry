"""
Game class with state management and coordination.
Handles main game loop, event processing, rendering, and state transitions.
"""

import pygame
from typing import Optional

from snake import Snake
from food import Food
from constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    GRID_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
    FPS,
    SNAKE_SPEED,
    COLORS,
    DIRECTION_UP,
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    GameState,
    SCORE_PER_FOOD,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
)
from utils import grid_to_pixel, get_grid_rect


class Game:
    """
    Main game class coordinating all game components.

    Manages the game loop, state transitions, rendering, and
    event handling. Uses pygame for graphics and input.
    """

    def __init__(self):
        """Initialize the game."""
        # Initialize pygame
        pygame.init()

        # Set up display
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)

        # Set up clock for frame rate control
        self.clock = pygame.time.Clock()

        # Set up fonts
        self.font_large = pygame.font.Font(None, FONT_SIZE_LARGE)
        self.font_medium = pygame.font.Font(None, FONT_SIZE_MEDIUM)
        self.font_small = pygame.font.Font(None, FONT_SIZE_SMALL)

        # Initialize game state
        self.state: str = GameState.MENU
        self.running: bool = True
        self.score: int = 0
        self.high_score: int = 0

        # Movement timing
        self.move_timer: float = 0.0
        self.move_interval: float = 1.0 / SNAKE_SPEED

        # Initialize game entities
        self.snake: Optional[Snake] = None
        self.food: Optional[Food] = None

    def _init_game_entities(self) -> None:
        """Initialize or reset game entities for a new game."""
        self.snake = Snake()
        self.food = Food(avoid_positions=self.snake.get_body_positions())
        self.score = 0
        self.move_timer = 0.0

    def run(self) -> None:
        """
        Main game loop.

        Handles timing, events, updates, and rendering at consistent frame rate.
        """
        while self.running:
            # Calculate delta time
            dt = self.clock.tick(FPS) / 1000.0  # Convert to seconds

            # Handle events
            self.handle_events()

            # Update game state
            self.update(dt)

            # Render
            self.render()

        # Clean up
        pygame.quit()

    def handle_events(self) -> None:
        """
        Process all pygame events.

        Handles quit events, keyboard input, and state-specific controls.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._handle_key_press(event.key)

    def _handle_key_press(self, key: int) -> None:
        """
        Handle a key press event.

        Args:
            key: The pygame key constant
        """
        # Global controls
        if key == pygame.K_ESCAPE:
            self.running = False
            return

        # State-specific controls
        if self.state == GameState.MENU:
            self._handle_menu_input(key)
        elif self.state == GameState.PLAYING:
            self._handle_playing_input(key)
        elif self.state == GameState.PAUSED:
            self._handle_paused_input(key)
        elif self.state == GameState.GAME_OVER:
            self._handle_game_over_input(key)

    def _handle_menu_input(self, key: int) -> None:
        """Handle input in menu state."""
        if key == pygame.K_SPACE:
            self._start_game()

    def _handle_playing_input(self, key: int) -> None:
        """Handle input during gameplay."""
        if key == pygame.K_p:
            self.state = GameState.PAUSED
            return

        # Direction controls
        direction_map = {
            pygame.K_UP: DIRECTION_UP,
            pygame.K_DOWN: DIRECTION_DOWN,
            pygame.K_LEFT: DIRECTION_LEFT,
            pygame.K_RIGHT: DIRECTION_RIGHT,
            pygame.K_w: DIRECTION_UP,
            pygame.K_s: DIRECTION_DOWN,
            pygame.K_a: DIRECTION_LEFT,
            pygame.K_d: DIRECTION_RIGHT,
        }

        if key in direction_map and self.snake:
            self.snake.change_direction(direction_map[key])

    def _handle_paused_input(self, key: int) -> None:
        """Handle input in paused state."""
        if key in (pygame.K_p, pygame.K_SPACE):
            self.state = GameState.PLAYING

    def _handle_game_over_input(self, key: int) -> None:
        """Handle input in game over state."""
        if key == pygame.K_SPACE:
            self._start_game()
        elif key == pygame.K_m:
            self.state = GameState.MENU

    def _start_game(self) -> None:
        """Start a new game."""
        self._init_game_entities()
        self.state = GameState.PLAYING

    def update(self, dt: float) -> None:
        """
        Update game state.

        Args:
            dt: Delta time in seconds since last update
        """
        if self.state != GameState.PLAYING:
            return

        if not self.snake or not self.food:
            return

        # Update movement timer
        self.move_timer += dt

        # Move snake at fixed intervals
        if self.move_timer >= self.move_interval:
            self.move_timer -= self.move_interval
            self._move_snake()

    def _move_snake(self) -> None:
        """Move the snake and handle collisions."""
        if not self.snake or not self.food:
            return

        # Move snake
        new_head = self.snake.move()

        # Check for collisions
        if self.snake.check_collision():
            self._game_over()
            return

        # Check for food collision
        if self.food.check_collision(new_head):
            self.snake.grow()
            self.score += SCORE_PER_FOOD
            self.food.respawn(self.snake.get_body_positions())

    def _game_over(self) -> None:
        """Handle game over state transition."""
        if self.score > self.high_score:
            self.high_score = self.score
        self.state = GameState.GAME_OVER

    def render(self) -> None:
        """
        Render the current game state.

        Draws appropriate screen based on current state.
        """
        # Clear screen
        self.screen.fill(COLORS["background"])

        # Render based on state
        if self.state == GameState.MENU:
            self._render_menu()
        elif self.state == GameState.PLAYING:
            self._render_game()
        elif self.state == GameState.PAUSED:
            self._render_game()
            self._render_pause_overlay()
        elif self.state == GameState.GAME_OVER:
            self._render_game()
            self._render_game_over_overlay()

        # Update display
        pygame.display.flip()

    def _render_menu(self) -> None:
        """Render the main menu screen."""
        # Title
        title_text = self.font_large.render("SNAKE GAME", True, COLORS["text"])
        title_rect = title_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3))
        self.screen.blit(title_text, title_rect)

        # Instructions
        start_text = self.font_medium.render("Press SPACE to Start", True, COLORS["text"])
        start_rect = start_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(start_text, start_rect)

        # Controls info
        controls = [
            "Controls:",
            "Arrow Keys / WASD - Move",
            "P - Pause",
            "ESC - Quit",
        ]
        y_offset = WINDOW_HEIGHT * 2 // 3
        for line in controls:
            ctrl_text = self.font_small.render(line, True, COLORS["text"])
            ctrl_rect = ctrl_text.get_rect(center=(WINDOW_WIDTH // 2, y_offset))
            self.screen.blit(ctrl_text, ctrl_rect)
            y_offset += 30

        # High score
        if self.high_score > 0:
            hs_text = self.font_small.render(
                f"High Score: {self.high_score}", True, COLORS["score_text"]
            )
            hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
            self.screen.blit(hs_text, hs_rect)

    def _render_game(self) -> None:
        """Render the game playing screen."""
        # Draw grid lines (optional, for visual reference)
        self._draw_grid()

        # Draw snake
        if self.snake:
            self._draw_snake()

        # Draw food
        if self.food:
            self._draw_food()

        # Draw score
        self._draw_score()

    def _draw_grid(self) -> None:
        """Draw grid lines for visual reference."""
        for x in range(0, WINDOW_WIDTH, GRID_SIZE):
            pygame.draw.line(
                self.screen,
                COLORS["grid_line"],
                (x, 0),
                (x, WINDOW_HEIGHT)
            )
        for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
            pygame.draw.line(
                self.screen,
                COLORS["grid_line"],
                (0, y),
                (WINDOW_WIDTH, y)
            )

    def _draw_snake(self) -> None:
        """Draw the snake on the screen."""
        if not self.snake:
            return

        body_positions = self.snake.get_body_positions()

        for i, pos in enumerate(body_positions):
            x, y = grid_to_pixel(pos[0], pos[1])
            rect = pygame.Rect(x, y, GRID_SIZE - 1, GRID_SIZE - 1)

            # Head is different color
            color = COLORS["snake_head"] if i == 0 else COLORS["snake_body"]
            pygame.draw.rect(self.screen, color, rect)

    def _draw_food(self) -> None:
        """Draw the food on the screen."""
        if not self.food:
            return

        pos = self.food.get_position()
        x, y = grid_to_pixel(pos[0], pos[1])
        rect = pygame.Rect(x, y, GRID_SIZE - 1, GRID_SIZE - 1)
        pygame.draw.rect(self.screen, COLORS["food"], rect)

    def _draw_score(self) -> None:
        """Draw the current score."""
        score_text = self.font_small.render(
            f"Score: {self.score}", True, COLORS["score_text"]
        )
        self.screen.blit(score_text, (10, 10))

    def _render_pause_overlay(self) -> None:
        """Render pause overlay on top of game."""
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Pause text
        pause_text = self.font_large.render("PAUSED", True, COLORS["text"])
        pause_rect = pause_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(pause_text, pause_rect)

        # Resume instruction
        resume_text = self.font_medium.render(
            "Press P or SPACE to Resume", True, COLORS["text"]
        )
        resume_rect = resume_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50)
        )
        self.screen.blit(resume_text, resume_rect)

    def _render_game_over_overlay(self) -> None:
        """Render game over overlay on top of game."""
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Game over text
        go_text = self.font_large.render("GAME OVER", True, COLORS["game_over_text"])
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3))
        self.screen.blit(go_text, go_rect)

        # Final score
        score_text = self.font_medium.render(
            f"Final Score: {self.score}", True, COLORS["score_text"]
        )
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(score_text, score_rect)

        # High score
        if self.score >= self.high_score and self.score > 0:
            hs_text = self.font_medium.render("NEW HIGH SCORE!", True, COLORS["score_text"])
            hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 40))
            self.screen.blit(hs_text, hs_rect)

        # Restart instruction
        restart_text = self.font_small.render(
            "Press SPACE to Play Again", True, COLORS["text"]
        )
        restart_rect = restart_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT * 2 // 3)
        )
        self.screen.blit(restart_text, restart_rect)

        # Menu instruction
        menu_text = self.font_small.render("Press M for Menu", True, COLORS["text"])
        menu_rect = menu_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT * 2 // 3 + 30)
        )
        self.screen.blit(menu_text, menu_rect)

    def get_state(self) -> str:
        """Get the current game state."""
        return self.state

    def get_score(self) -> int:
        """Get the current score."""
        return self.score

    def get_high_score(self) -> int:
        """Get the high score."""
        return self.high_score

    def is_running(self) -> bool:
        """Check if the game is still running."""
        return self.running
