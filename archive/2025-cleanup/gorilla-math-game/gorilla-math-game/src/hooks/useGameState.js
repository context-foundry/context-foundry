import { useState, useCallback } from 'react';
import { generateProblem, selectRandomOperation } from '../utils/problemGenerator';
import { FEEDBACK_MESSAGES, FEEDBACK_DURATION } from '../utils/constants';

/**
 * Custom hook for managing game state and logic
 * @returns {Object} Game state and control functions
 */
export function useGameState() {
  const [gameState, setGameState] = useState({
    currentProblem: null,
    userAnswer: '',
    score: 0,
    streak: 0,
    totalAttempts: 0,
    feedback: {
      show: false,
      isCorrect: false,
      message: ''
    },
    gameStarted: false
  });

  /**
   * Start a new game
   */
  const startGame = useCallback(() => {
    const operation = selectRandomOperation();
    const problem = generateProblem(operation);

    setGameState({
      currentProblem: problem,
      userAnswer: '',
      score: 0,
      streak: 0,
      totalAttempts: 0,
      feedback: {
        show: false,
        isCorrect: false,
        message: ''
      },
      gameStarted: true
    });
  }, []);

  /**
   * Generate the next problem
   */
  const nextProblem = useCallback(() => {
    const operation = selectRandomOperation();
    const problem = generateProblem(operation);

    setGameState(prev => ({
      ...prev,
      currentProblem: problem,
      userAnswer: '',
      feedback: {
        show: false,
        isCorrect: false,
        message: ''
      }
    }));
  }, []);

  /**
   * Submit user's answer and validate
   * @param {string|number} answer - User's answer
   */
  const submitAnswer = useCallback((answer) => {
    if (!gameState.currentProblem) return;

    const userAnswerNum = parseInt(answer, 10);
    const isCorrect = userAnswerNum === gameState.currentProblem.correctAnswer;

    // Select random message
    const messages = isCorrect ? FEEDBACK_MESSAGES.correct : FEEDBACK_MESSAGES.incorrect;
    const randomMessage = messages[Math.floor(Math.random() * messages.length)];

    // Build feedback message
    let message = randomMessage;
    if (!isCorrect) {
      message = `${randomMessage} The answer is ${gameState.currentProblem.correctAnswer}.`;
    }

    // Update state
    setGameState(prev => ({
      ...prev,
      score: isCorrect ? prev.score + 1 : prev.score,
      streak: isCorrect ? prev.streak + 1 : 0,
      totalAttempts: prev.totalAttempts + 1,
      feedback: {
        show: true,
        isCorrect,
        message
      }
    }));

    // Auto-generate next problem after delay
    setTimeout(() => {
      nextProblem();
    }, FEEDBACK_DURATION);
  }, [gameState.currentProblem, nextProblem]);

  /**
   * Reset the game to initial state
   */
  const resetGame = useCallback(() => {
    setGameState({
      currentProblem: null,
      userAnswer: '',
      score: 0,
      streak: 0,
      totalAttempts: 0,
      feedback: {
        show: false,
        isCorrect: false,
        message: ''
      },
      gameStarted: false
    });
  }, []);

  return {
    gameState,
    startGame,
    submitAnswer,
    nextProblem,
    resetGame
  };
}
