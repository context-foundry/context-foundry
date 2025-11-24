import React, { useState, useRef, useEffect } from 'react';

/**
 * AnswerInput Component
 * Captures user numeric input with large touch-friendly controls
 */
export default function AnswerInput({ onSubmit, disabled }) {
  const [answer, setAnswer] = useState('');
  const inputRef = useRef(null);

  // Auto-focus input when component mounts or re-enables
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (answer.trim() !== '' && !disabled) {
      onSubmit(answer);
      setAnswer(''); // Clear input after submission
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="answer-input"
            className="block text-2xl md:text-3xl font-bold text-gray-800 mb-3"
          >
            Your Answer:
          </label>
          <input
            ref={inputRef}
            id="answer-input"
            type="number"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className="w-full text-4xl md:text-5xl font-bold text-center py-4 px-6 border-4 border-blue-400 rounded-2xl focus:outline-none focus:ring-4 focus:ring-blue-500 disabled:bg-gray-200 disabled:cursor-not-allowed"
            placeholder="?"
            min="0"
            max="100"
            aria-label="Enter your answer"
          />
        </div>
        <button
          type="submit"
          disabled={disabled || answer.trim() === ''}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white text-3xl md:text-4xl font-bold py-6 px-8 rounded-2xl shadow-lg transform transition hover:scale-105 focus:outline-none focus:ring-4 focus:ring-blue-400"
          style={{ minHeight: '60px' }}
          aria-label="Check your answer"
        >
          Check Answer ✓
        </button>
      </form>
    </div>
  );
}
