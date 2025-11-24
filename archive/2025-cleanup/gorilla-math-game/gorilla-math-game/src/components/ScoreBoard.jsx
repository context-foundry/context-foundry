import React from 'react';

/**
 * ScoreBoard Component
 * Persistent display of score and streak
 */
export default function ScoreBoard({ score, totalAttempts, streak }) {
  const percentage = totalAttempts > 0
    ? Math.round((score / totalAttempts) * 100)
    : 0;

  const showStreakFire = streak >= 3;

  return (
    <div className="fixed top-4 right-4 bg-white/90 backdrop-blur-sm border-4 border-purple-400 rounded-2xl p-4 shadow-xl z-50">
      <div className="space-y-2">
        <div className="text-center">
          <p className="text-sm font-semibold text-gray-600">SCORE</p>
          <p className="text-3xl font-bold text-purple-700">
            {score} / {totalAttempts}
          </p>
          <p className="text-lg text-gray-700">{percentage}%</p>
        </div>

        {streak > 0 && (
          <div className="text-center border-t-2 border-purple-300 pt-2">
            <p className="text-sm font-semibold text-gray-600">STREAK</p>
            <p className="text-2xl font-bold text-orange-600">
              {streak} {showStreakFire && '🔥'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
