'use client';

import React, { useState } from 'react';
import { FillBlankExercise as FillBlankExerciseType } from '@/types/learning';
import { BlankInput } from './BlankInput';
import { CheckCircle2, XCircle, RotateCcw } from 'lucide-react';

interface FillBlankExerciseProps {
  exercise: FillBlankExerciseType;
  onComplete: (result: { score: number; timeTaken: number }) => void;
}

interface BlankAnswer {
  sentenceId: string;
  blankId: string;
  value: string;
  isCorrect: boolean | null;
}

export function FillBlankExercise({ exercise, onComplete }: FillBlankExerciseProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [validated, setValidated] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);
  const [startTime] = useState(Date.now());

  // Get total number of blanks
  const totalBlanks = exercise.sentences.reduce(
    (sum, sentence) => sum + sentence.blanks.length,
    0
  );

  const handleAnswerChange = (blankId: string, value: string) => {
    setAnswers((prev) => ({
      ...prev,
      [blankId]: value,
    }));
  };

  const validateAnswer = (blankId: string, correctAnswers: string[], caseSensitive: boolean) => {
    const userAnswer = answers[blankId] || '';

    if (!userAnswer.trim()) {
      return null;
    }

    const normalizedAnswer = caseSensitive ? userAnswer : userAnswer.toLowerCase();
    const normalizedCorrect = correctAnswers.map((ans) =>
      caseSensitive ? ans : ans.toLowerCase()
    );

    return normalizedCorrect.some((correct) =>
      normalizedAnswer.trim() === correct.trim()
    );
  };

  const handleSubmit = () => {
    const newValidated: Record<string, boolean> = {};

    exercise.sentences.forEach((sentence) => {
      sentence.blanks.forEach((blank) => {
        const isCorrect = validateAnswer(
          blank.id,
          blank.correctAnswers,
          blank.caseSensitive
        );
        if (isCorrect !== null) {
          newValidated[blank.id] = isCorrect;
        }
      });
    });

    setValidated(newValidated);
    setSubmitted(true);

    // Calculate score
    const correctCount = Object.values(newValidated).filter((v) => v === true).length;
    const score = Math.round((correctCount / totalBlanks) * 100);
    const timeTaken = Math.round((Date.now() - startTime) / 1000);

    onComplete({ score, timeTaken });
  };

  const handleReset = () => {
    setAnswers({});
    setValidated({});
    setSubmitted(false);
  };

  const answeredCount = Object.keys(answers).filter((key) => answers[key].trim()).length;
  const canSubmit = answeredCount === totalBlanks && !submitted;

  const renderSentenceWithBlanks = (sentence: typeof exercise.sentences[0]) => {
    const parts = sentence.template.split(/(\{\{blank\}\})/g);
    let blankIndex = 0;

    return (
      <div className="text-lg leading-relaxed">
        {parts.map((part, index) => {
          if (part === '{{blank}}') {
            const blank = sentence.blanks[blankIndex];
            blankIndex++;

            if (!blank) return null;

            return (
              <BlankInput
                key={blank.id}
                blankId={blank.id}
                value={answers[blank.id] || ''}
                onChange={handleAnswerChange}
                isCorrect={validated[blank.id]}
                disabled={submitted}
                hint={blank.hint}
              />
            );
          }

          return <span key={index}>{part}</span>;
        })}
      </div>
    );
  };

  const correctCount = Object.values(validated).filter((v) => v === true).length;
  const score = totalBlanks > 0 ? Math.round((correctCount / totalBlanks) * 100) : 0;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">Instructions</h3>
        <p className="text-sm text-blue-800">
          Fill in the blanks with the correct terms. Click the hint button (?) if you need help.
        </p>
      </div>

      {/* Score Display (if submitted) */}
      {submitted && (
        <div
          className={`rounded-lg p-6 text-center ${
            score >= 70
              ? 'bg-gradient-to-br from-green-50 to-green-100 border-2 border-green-200'
              : 'bg-gradient-to-br from-yellow-50 to-yellow-100 border-2 border-yellow-200'
          }`}
        >
          <div className="flex justify-center mb-4">
            {score >= 70 ? (
              <CheckCircle2 className="h-12 w-12 text-green-600" aria-hidden="true" />
            ) : (
              <XCircle className="h-12 w-12 text-yellow-600" aria-hidden="true" />
            )}
          </div>
          <h3 className="text-2xl font-bold text-gray-900 mb-2">
            {score >= 70 ? 'Great Job!' : 'Keep Practicing!'}
          </h3>
          <div className="text-4xl font-bold text-blue-600 mb-2">{score}%</div>
          <p className="text-sm text-gray-700">
            {correctCount} out of {totalBlanks} correct
          </p>
        </div>
      )}

      {/* Sentences */}
      <div className="space-y-6">
        {exercise.sentences.map((sentence, index) => (
          <div
            key={sentence.id}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
          >
            <div className="mb-4">
              <span className="inline-block px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium mb-4">
                Sentence {index + 1}
              </span>
            </div>

            {/* Sentence with blanks */}
            {renderSentenceWithBlanks(sentence)}

            {/* Explanation (shown after submission) */}
            {submitted && sentence.explanation && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-2">Explanation</h4>
                <p className="text-sm text-blue-800">{sentence.explanation}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="text-sm text-gray-600">
          {answeredCount} / {totalBlanks} blanks filled
        </div>

        <div className="flex gap-3">
          {submitted ? (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Try again"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Try Again
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="px-6 py-3 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px] focus:outline-none focus:ring-2 focus:ring-green-500"
              aria-label="Submit answers"
            >
              Submit Answers
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
