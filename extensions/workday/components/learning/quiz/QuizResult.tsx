'use client';

import React from 'react';
import { QuizResult } from '@/types/learning';
import { CheckCircle2, XCircle, Trophy, RotateCcw, Clock } from 'lucide-react';
import { MultipleChoice } from './MultipleChoice';

interface QuizResultProps {
  result: QuizResult;
  passingScore: number;
  onRetry: () => void;
}

export function QuizResult({ result, passingScore, onRetry }: QuizResultProps) {
  const scorePercentage = result.score;
  const isPassed = result.passed;

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Score Card */}
      <div
        className={`rounded-lg p-8 text-center ${
          isPassed
            ? 'bg-gradient-to-br from-green-50 to-green-100 border-2 border-green-200'
            : 'bg-gradient-to-br from-red-50 to-red-100 border-2 border-red-200'
        }`}
      >
        <div className="flex justify-center mb-4">
          {isPassed ? (
            <Trophy className="h-16 w-16 text-green-600" aria-hidden="true" />
          ) : (
            <XCircle className="h-16 w-16 text-red-600" aria-hidden="true" />
          )}
        </div>

        <h2 className="text-3xl font-bold text-gray-900 mb-2">
          {isPassed ? 'Congratulations!' : 'Keep Trying!'}
        </h2>

        <p className="text-lg text-gray-700 mb-6">
          {isPassed
            ? 'You passed the quiz!'
            : `You need ${passingScore}% to pass. Review the material and try again.`}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-2xl mx-auto">
          {/* Score */}
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <div className="text-4xl font-bold text-blue-600 mb-1">{scorePercentage}%</div>
            <div className="text-sm text-gray-600">Score</div>
          </div>

          {/* Correct Answers */}
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <div className="text-4xl font-bold text-green-600 mb-1">
              {result.correctAnswers}/{result.totalQuestions}
            </div>
            <div className="text-sm text-gray-600">Correct</div>
          </div>

          {/* Time Taken */}
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <div className="text-4xl font-bold text-purple-600 mb-1 flex items-center justify-center gap-2">
              <Clock className="h-8 w-8" aria-hidden="true" />
              {formatTime(result.timeTaken)}
            </div>
            <div className="text-sm text-gray-600">Time</div>
          </div>
        </div>

        {/* Retry Button */}
        <button
          onClick={onRetry}
          className="mt-6 inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Retry quiz"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Retry Quiz
        </button>
      </div>

      {/* Question Breakdown */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-6">Question Breakdown</h3>

        <div className="space-y-6">
          {result.questionResults.map((qResult, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border-2 ${
                qResult.isCorrect
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              <div className="flex items-start gap-3 mb-4">
                <div className="flex-shrink-0 mt-1">
                  {qResult.isCorrect ? (
                    <CheckCircle2 className="h-6 w-6 text-green-600" aria-hidden="true" />
                  ) : (
                    <XCircle className="h-6 w-6 text-red-600" aria-hidden="true" />
                  )}
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900 mb-2">
                    Question {index + 1}
                  </h4>
                  <MultipleChoice
                    question={qResult.question}
                    selectedAnswer={qResult.selectedAnswer}
                    onAnswerSelect={() => {}}
                    showFeedback={true}
                    disabled={true}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
