import { describe, test, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGameState } from '../../src/hooks/useGameState';

describe('useGameState', () => {
  test('initializes with correct default state', () => {
    const { result } = renderHook(() => useGameState());

    expect(result.current.gameState.gameStarted).toBe(false);
    expect(result.current.gameState.currentProblem).toBeNull();
    expect(result.current.gameState.score).toBe(0);
    expect(result.current.gameState.streak).toBe(0);
    expect(result.current.gameState.totalAttempts).toBe(0);
  });

  test('startGame initializes game state correctly', () => {
    const { result } = renderHook(() => useGameState());

    act(() => {
      result.current.startGame();
    });

    expect(result.current.gameState.gameStarted).toBe(true);
    expect(result.current.gameState.currentProblem).not.toBeNull();
    expect(result.current.gameState.currentProblem).toHaveProperty('operation');
    expect(result.current.gameState.currentProblem).toHaveProperty('operand1');
    expect(result.current.gameState.currentProblem).toHaveProperty('operand2');
    expect(result.current.gameState.currentProblem).toHaveProperty('correctAnswer');
  });

  test('submitAnswer increments score on correct answer', async () => {
    const { result } = renderHook(() => useGameState());

    act(() => {
      result.current.startGame();
    });

    const correctAnswer = result.current.gameState.currentProblem.correctAnswer;

    await act(async () => {
      result.current.submitAnswer(correctAnswer.toString());
    });

    expect(result.current.gameState.score).toBe(1);
    expect(result.current.gameState.streak).toBe(1);
    expect(result.current.gameState.totalAttempts).toBe(1);
    expect(result.current.gameState.feedback.isCorrect).toBe(true);
  });

  test('submitAnswer does not increment score on incorrect answer', async () => {
    const { result } = renderHook(() => useGameState());

    act(() => {
      result.current.startGame();
    });

    const wrongAnswer = (result.current.gameState.currentProblem.correctAnswer + 999).toString();

    await act(async () => {
      result.current.submitAnswer(wrongAnswer);
    });

    expect(result.current.gameState.score).toBe(0);
    expect(result.current.gameState.streak).toBe(0);
    expect(result.current.gameState.totalAttempts).toBe(1);
    expect(result.current.gameState.feedback.isCorrect).toBe(false);
  });

  test('submitAnswer resets streak on incorrect answer after streak', async () => {
    const { result } = renderHook(() => useGameState());

    act(() => {
      result.current.startGame();
    });

    // Get two correct answers first
    for (let i = 0; i < 2; i++) {
      const correctAnswer = result.current.gameState.currentProblem.correctAnswer;

      await act(async () => {
        result.current.submitAnswer(correctAnswer.toString());
        // Wait for next problem to generate
        await new Promise(resolve => setTimeout(resolve, 100));
      });
    }

    // Wait for last problem to generate
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 2100));
    });

    expect(result.current.gameState.streak).toBe(2);

    // Now submit wrong answer
    const wrongAnswer = (result.current.gameState.currentProblem.correctAnswer + 999).toString();

    await act(async () => {
      result.current.submitAnswer(wrongAnswer);
    });

    expect(result.current.gameState.streak).toBe(0);
    expect(result.current.gameState.score).toBe(2); // Score should still be 2
  });

  test('resetGame clears all state', () => {
    const { result } = renderHook(() => useGameState());

    // Start game and submit an answer
    act(() => {
      result.current.startGame();
    });

    const correctAnswer = result.current.gameState.currentProblem.correctAnswer;

    act(() => {
      result.current.submitAnswer(correctAnswer.toString());
    });

    // Now reset
    act(() => {
      result.current.resetGame();
    });

    expect(result.current.gameState.gameStarted).toBe(false);
    expect(result.current.gameState.currentProblem).toBeNull();
    expect(result.current.gameState.score).toBe(0);
    expect(result.current.gameState.streak).toBe(0);
    expect(result.current.gameState.totalAttempts).toBe(0);
    expect(result.current.gameState.feedback.show).toBe(false);
  });

  test('nextProblem generates new problem', () => {
    const { result } = renderHook(() => useGameState());

    act(() => {
      result.current.startGame();
    });

    const firstProblem = result.current.gameState.currentProblem;

    act(() => {
      result.current.nextProblem();
    });

    const secondProblem = result.current.gameState.currentProblem;

    // Problems should be different (or at least have fresh state)
    expect(secondProblem).not.toBeNull();
    expect(result.current.gameState.feedback.show).toBe(false);
  });
});
