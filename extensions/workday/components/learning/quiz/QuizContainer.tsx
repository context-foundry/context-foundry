'use client';

import React, { useReducer, useEffect } from 'react';
import { Quiz, QuizState, QuizResult } from '@/types/learning';
import { MultipleChoice } from './MultipleChoice';
import { QuizResult as QuizResultComponent } from './QuizResult';
import { ProgressBar } from '../shared/ProgressBar';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface QuizContainerProps {
  quiz: Quiz;
  onComplete: (result: QuizResult) => void;
}

type QuizAction =
  | { type: 'SELECT_ANSWER'; questionIndex: number; answerIndex: number }
  | { type: 'NEXT_QUESTION' }
  | { type: 'PREVIOUS_QUESTION' }
  | { type: 'SUBMIT_QUIZ' }
  | { type: 'RETRY_QUIZ' };

const initialState: QuizState = {
  currentQuestionIndex: 0,
  answers: {},
  score: null,
  completed: false,
  startedAt: Date.now(),
  completedAt: null,
};

function quizReducer(state: QuizState, action: QuizAction): QuizState {
  switch (action.type) {
    case 'SELECT_ANSWER':
      return {
        ...state,
        answers: {
          ...state.answers,
          [action.questionIndex]: action.answerIndex,
        },
      };

    case 'NEXT_QUESTION':
      return {
        ...state,
        currentQuestionIndex: state.currentQuestionIndex + 1,
      };

    case 'PREVIOUS_QUESTION':
      return {
        ...state,
        currentQuestionIndex: Math.max(0, state.currentQuestionIndex - 1),
      };

    case 'SUBMIT_QUIZ':
      return {
        ...state,
        completed: true,
        completedAt: Date.now(),
      };

    case 'RETRY_QUIZ':
      return {
        ...initialState,
        startedAt: Date.now(),
      };

    default:
      return state;
  }
}

export function QuizContainer({ quiz, onComplete }: QuizContainerProps) {
  const [state, dispatch] = useReducer(quizReducer, initialState);

  const currentQuestion = quiz.questions[state.currentQuestionIndex];
  const totalQuestions = quiz.questions.length;
  const progress = ((state.currentQuestionIndex + 1) / totalQuestions) * 100;
  const answeredCount = Object.keys(state.answers).length;
  const canSubmit = answeredCount === totalQuestions;

  // Calculate results when quiz is submitted
  useEffect(() => {
    if (state.completed && state.completedAt) {
      const correctAnswers = quiz.questions.filter(
        (q, idx) => state.answers[idx] === q.correctAnswer
      ).length;

      const score = Math.round((correctAnswers / totalQuestions) * 100);
      const timeTaken = Math.round((state.completedAt - state.startedAt) / 1000);

      const result: QuizResult = {
        score,
        totalQuestions,
        correctAnswers,
        passed: score >= quiz.passingScore,
        timeTaken,
        questionResults: quiz.questions.map((question, idx) => ({
          question,
          selectedAnswer: state.answers[idx] ?? -1,
          isCorrect: state.answers[idx] === question.correctAnswer,
        })),
      };

      onComplete(result);
    }
  }, [state.completed, state.completedAt, quiz, state.answers, state.startedAt, totalQuestions, onComplete]);

  const handleSelectAnswer = (answerIndex: number) => {
    dispatch({
      type: 'SELECT_ANSWER',
      questionIndex: state.currentQuestionIndex,
      answerIndex,
    });
  };

  const handleNext = () => {
    if (state.currentQuestionIndex < totalQuestions - 1) {
      dispatch({ type: 'NEXT_QUESTION' });
    }
  };

  const handlePrevious = () => {
    if (state.currentQuestionIndex > 0) {
      dispatch({ type: 'PREVIOUS_QUESTION' });
    }
  };

  const handleSubmit = () => {
    if (canSubmit) {
      dispatch({ type: 'SUBMIT_QUIZ' });
    }
  };

  const handleRetry = () => {
    dispatch({ type: 'RETRY_QUIZ' });
  };

  if (state.completed) {
    const correctAnswers = quiz.questions.filter(
      (q, idx) => state.answers[idx] === q.correctAnswer
    ).length;
    const score = Math.round((correctAnswers / totalQuestions) * 100);
    const timeTaken = state.completedAt ? Math.round((state.completedAt - state.startedAt) / 1000) : 0;

    const result: QuizResult = {
      score,
      totalQuestions,
      correctAnswers,
      passed: score >= quiz.passingScore,
      timeTaken,
      questionResults: quiz.questions.map((question, idx) => ({
        question,
        selectedAnswer: state.answers[idx] ?? -1,
        isCorrect: state.answers[idx] === question.correctAnswer,
      })),
    };

    return <QuizResultComponent result={result} passingScore={quiz.passingScore} onRetry={handleRetry} />;
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Progress Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-gray-700">
            Question {state.currentQuestionIndex + 1} of {totalQuestions}
          </span>
          <span className="text-sm text-gray-600">
            {answeredCount} / {totalQuestions} answered
          </span>
        </div>
        <ProgressBar value={progress} className="h-2" />
      </div>

      {/* Question */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <MultipleChoice
          question={currentQuestion}
          selectedAnswer={state.answers[state.currentQuestionIndex]}
          onAnswerSelect={handleSelectAnswer}
        />
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={handlePrevious}
          disabled={state.currentQuestionIndex === 0}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Previous question"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Previous
        </button>

        {state.currentQuestionIndex < totalQuestions - 1 ? (
          <button
            onClick={handleNext}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Next question"
          >
            Next
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-6 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px] focus:outline-none focus:ring-2 focus:ring-green-500"
            aria-label="Submit quiz"
          >
            Submit Quiz
          </button>
        )}
      </div>

      {/* Submit Warning */}
      {state.currentQuestionIndex === totalQuestions - 1 && !canSubmit && (
        <p className="mt-4 text-sm text-amber-600 text-center">
          Please answer all questions before submitting
        </p>
      )}
    </div>
  );
}
