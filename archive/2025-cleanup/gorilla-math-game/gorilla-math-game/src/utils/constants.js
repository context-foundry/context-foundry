// Game configuration constants

export const PROBLEM_RANGES = {
  addition: { min: 0, max: 20, maxResult: 25 },
  subtraction: { min: 0, max: 20 },
  multiplication: { min: 1, max: 5 }
};

export const FEEDBACK_MESSAGES = {
  correct: [
    "Great job! 🎉",
    "You got it! 🌟",
    "Perfect! 🍌",
    "Amazing work! 🦍",
    "Fantastic! ⭐"
  ],
  incorrect: [
    "Not quite! Try the next one!",
    "Almost! Let's try another!",
    "Good try! Here's another problem!"
  ]
};

export const FEEDBACK_DURATION = 2000; // milliseconds

export const GORILLA_STATES = {
  THINKING: 'thinking',
  HAPPY: 'happy',
  OOPS: 'oops'
};
