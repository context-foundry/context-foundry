import React, { useEffect } from 'react';
import WelcomeScreen from './components/WelcomeScreen';
import GameContainer from './components/GameContainer';
import { useGameState } from './hooks/useGameState';
import { soundManager } from './utils/soundManager';
import './App.css';

/**
 * App Component
 * Root component managing global game state and routing
 */
function App() {
  const { gameState, startGame, submitAnswer, resetGame } = useGameState();

  // Initialize sound manager on first user interaction
  useEffect(() => {
    const initSound = () => {
      soundManager.init();
      // Remove listener after first interaction
      document.removeEventListener('click', initSound);
    };
    document.addEventListener('click', initSound);

    return () => {
      document.removeEventListener('click', initSound);
    };
  }, []);

  // Handle global keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      // ESC key to reset game
      if (e.key === 'Escape' && gameState.gameStarted) {
        resetGame();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, [gameState.gameStarted, resetGame]);

  // Handle answer submission with sound effects
  const handleSubmitAnswer = (answer) => {
    submitAnswer(answer);

    // Play sound based on correctness (will be determined in next tick)
    setTimeout(() => {
      if (gameState.feedback.isCorrect) {
        soundManager.playSuccess();
      } else {
        soundManager.playError();
      }
    }, 100);
  };

  return (
    <div className="App">
      {!gameState.gameStarted ? (
        <WelcomeScreen onStart={startGame} />
      ) : (
        <GameContainer
          gameState={gameState}
          onSubmitAnswer={handleSubmitAnswer}
          onReset={resetGame}
        />
      )}
    </div>
  );
}

export default App;
