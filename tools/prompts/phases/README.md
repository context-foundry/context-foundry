# Snake Game

A classic Snake game implementation using Python and pygame library with object-oriented design.

## Features

- Smooth movement mechanics
- Collision detection (walls and self-collision)
- Score tracking
- Game state management (Menu, Playing, Paused, Game Over)
- Restart functionality

## Requirements

- Python 3.8+
- pygame 2.5.0+

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Game

```bash
python main.py
```

## Controls

- **Arrow Keys**: Control snake direction
- **SPACE**: Start game / Restart after game over
- **P**: Pause/Resume game
- **ESC**: Quit game

## Project Structure

```
.
├── main.py          # Application entry point
├── game.py          # Game class with state management
├── snake.py         # Snake entity with movement mechanics
├── food.py          # Food entity with spawning logic
├── constants.py     # Game constants and configuration
├── utils.py         # Utility functions
├── assets/          # Asset directory
│   └── sounds/      # Sound effects
├── tests/           # Test directory
│   ├── test_snake.py
│   ├── test_food.py
│   ├── test_game.py
│   └── test_utils.py
└── requirements.txt # Python dependencies
```

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT License
