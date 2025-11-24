import React from 'react';
import { GORILLA_STATES } from '../utils/constants';

/**
 * GorillaCharacter Component
 * Animated mascot providing visual engagement
 */
export default function GorillaCharacter({ state }) {
  const getGorillaEmoji = () => {
    switch (state) {
      case GORILLA_STATES.HAPPY:
        return '🎉🦍🎉';
      case GORILLA_STATES.OOPS:
        return '🤔🦍';
      case GORILLA_STATES.THINKING:
      default:
        return '🦍';
    }
  };

  const getAltText = () => {
    switch (state) {
      case GORILLA_STATES.HAPPY:
        return 'Happy gorilla celebrating your correct answer';
      case GORILLA_STATES.OOPS:
        return 'Thoughtful gorilla encouraging you to try again';
      case GORILLA_STATES.THINKING:
      default:
        return 'Gorilla thinking about the math problem';
    }
  };

  const getAnimationClass = () => {
    switch (state) {
      case GORILLA_STATES.HAPPY:
        return 'animate-bounce';
      case GORILLA_STATES.OOPS:
        return 'animate-pulse';
      default:
        return '';
    }
  };

  return (
    <div className="flex justify-center items-center p-8" role="img" aria-label={getAltText()}>
      <div
        className={`text-8xl md:text-9xl transition-all duration-300 ${getAnimationClass()}`}
      >
        {getGorillaEmoji()}
      </div>
    </div>
  );
}
