import React from 'react';

/**
 * FeedbackDisplay Component
 * Shows immediate correctness feedback with encouraging messages
 */
export default function FeedbackDisplay({ isCorrect, show, message }) {
  if (!show) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`
        w-full max-w-2xl mx-auto p-6 md:p-8 rounded-3xl shadow-2xl
        transform transition-all duration-300 ease-out
        ${show ? 'scale-100 opacity-100' : 'scale-90 opacity-0'}
        ${isCorrect
          ? 'bg-gradient-to-r from-green-400 to-green-500 border-4 border-green-600'
          : 'bg-gradient-to-r from-orange-400 to-yellow-500 border-4 border-orange-600'
        }
      `}
      style={{
        animation: show ? 'fadeInScale 0.3s ease-out' : 'none'
      }}
    >
      <div className="text-center">
        <div className="text-6xl md:text-8xl mb-4">
          {isCorrect ? '🎉' : '💭'}
        </div>
        <p className="text-3xl md:text-4xl font-bold text-white drop-shadow-lg">
          {message}
        </p>
      </div>
    </div>
  );
}
