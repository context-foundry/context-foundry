import React from 'react';

/**
 * WelcomeScreen Component
 * Initial screen with "Start Game" button
 */
export default function WelcomeScreen({ onStart }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-yellow-100 to-green-100 flex items-center justify-center p-4">
      <div className="text-center">
        <h1 className="text-6xl md:text-8xl font-bold text-green-800 mb-4">
          🦍 Gorilla Math Game
        </h1>
        <p className="text-2xl md:text-3xl text-gray-700 mb-8">
          Practice your math skills with our friendly gorilla!
        </p>
        <div className="mb-8 text-8xl">
          🦍
        </div>
        <button
          onClick={onStart}
          className="bg-green-600 hover:bg-green-700 text-white text-3xl font-bold py-6 px-12 rounded-2xl shadow-lg transform transition hover:scale-105 focus:outline-none focus:ring-4 focus:ring-green-400"
          aria-label="Start the math game"
        >
          Start Game! 🍌
        </button>
        <div className="mt-8 text-lg text-gray-600">
          <p>Addition • Subtraction • Multiplication</p>
          <p className="mt-2">Perfect for 2nd graders!</p>
        </div>
      </div>
    </div>
  );
}
