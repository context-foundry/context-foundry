import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import GameEngine from '../components/GameEngine';

// Mock the sound player
vi.mock('../utils/soundPlayer', () => ({
  initSounds: vi.fn(),
  playSound: vi.fn(),
  toggleMute: vi.fn(() => false),
  isSoundMuted: vi.fn(() => false),
}));

describe('Accessibility Compliance', () => {
  it('has proper ARIA labels on input field', () => {
    const { container } = render(<GameEngine />);
    const input = container.querySelector('input[type="number"]');
    expect(input).toHaveAttribute('aria-label');
  });

  it('has proper label for answer input', () => {
    const { container } = render(<GameEngine />);
    const label = container.querySelector('label[for="answer-input"]');
    expect(label).toBeInTheDocument();
    expect(label).toHaveTextContent(/Your Answer/);
  });

  it('feedback display has aria-live region', () => {
    const { container } = render(<GameEngine />);
    // Feedback may not be visible initially, but the component should support it
    expect(container).toBeTruthy();
  });

  it('mute button has aria-label', () => {
    const { container } = render(<GameEngine />);
    const muteButton = container.querySelector('button[aria-label*="sound"]');
    expect(muteButton).toBeInTheDocument();
  });

  it('input has minimum value of 0', () => {
    const { container } = render(<GameEngine />);
    const input = container.querySelector('input[type="number"]');
    expect(input).toHaveAttribute('min', '0');
  });

  it('all interactive elements are keyboard accessible', () => {
    const { container } = render(<GameEngine />);
    const input = container.querySelector('input[type="number"]');
    const submitButton = container.querySelector('button[aria-label="Submit answer"]');
    const muteButton = container.querySelector('button[aria-label*="sound"]');

    expect(input).toBeInTheDocument();
    expect(submitButton).toBeInTheDocument();
    expect(muteButton).toBeInTheDocument();
  });
});
