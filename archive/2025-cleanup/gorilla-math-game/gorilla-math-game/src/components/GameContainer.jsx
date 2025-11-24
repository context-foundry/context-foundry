import React from 'react';
import ProblemDisplay from './ProblemDisplay';
import AnswerInput from './AnswerInput';
import FeedbackDisplay from './FeedbackDisplay';
import ScoreBoard from './ScoreBoard';
import GorillaCharacter from './GorillaCharacter';
import { GORILLA_STATES } from '../utils/constants';

/**
 * GameContainer Component
 * Orchestrates active game layout and component interaction
 */
export default function GameContainer({ gameState, onSubmitAnswer, onReset }) {
  const { currentProblem, score, totalAttempts, streak, feedback } = gameState;

  if (!currentProblem) {
    return null;
  }

  // Determine gorilla state based on feedback
  const getGorillaState = () => {
    if (feedback.show) {
      return feedback.isCorrect ? GORILLA_STATES.HAPPY : GORILLA_STATES.OOPS;
    }
    return GORILLA_STATES.THINKING;
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-100 to-purple-100 p-4 md:p-8">
      {/* Score Board (fixed position) */}
      <ScoreBoard score={score} totalAttempts={totalAttempts} streak={streak} />

      {/* Main Game Area */}
      <div className="max-w-4xl mx-auto pt-16">
        {/* Reset Button */}
        <div className="flex justify-center mb-4">
          <button
            onClick={onReset}
            className="bg-gray-600 hover:bg-gray-700 text-white text-lg font-bold py-2 px-6 rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-gray-400"
            aria-label="Reset game and return to welcome screen"
          >
            ← Back to Start
          </button>
        </div>

        {/* Gorilla Character */}
        <GorillaCharacter state={getGorillaState()} />

        {/* Problem Display */}
        <div className="mb-8">
          <ProblemDisplay
            operation={currentProblem.operation}
            operand1={currentProblem.operand1}
            operand2={currentProblem.operand2}
          />
        </div>

        {/* Feedback Display (conditional) */}
        {feedback.show && (
          <div className="mb-8">
            <FeedbackDisplay
              isCorrect={feedback.isCorrect}
              show={feedback.show}
              message={feedback.message}
            />
          </div>
        )}

        {/* Answer Input (disabled during feedback) */}
        {!feedback.show && (
          <div className="mb-8">
            <AnswerInput
              onSubmit={onSubmitAnswer}
              disabled={feedback.show}
            />
          </div>
        )}

        {/* Instructions */}
        <div className="text-center text-gray-600 mt-8">
          <p className="text-lg">Type your answer and press Enter or click Check Answer!</p>
        </div>
      </div>
    </div>
  );
}
