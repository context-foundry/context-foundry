import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GameEngine from '../components/GameEngine';

// Mock the sound player to avoid audio errors in tests
vi.mock('../utils/soundPlayer', () => ({
  initSounds: vi.fn(),
  playSound: vi.fn(),
  toggleMute: vi.fn(() => false),
  isSoundMuted: vi.fn(() => false),
}));

describe('GameEngine Component', () => {
  it('renders initial problem and score', () => {
    render(<GameEngine />);
    expect(screen.getByText(/Score:/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Your Answer/)).toBeInTheDocument();
    expect(screen.getByTestId('problem-display')).toBeInTheDocument();
  });

  it('accepts user input in the answer field', () => {
    render(<GameEngine />);
    const input = screen.getByLabelText(/Your Answer/);
    fireEvent.change(input, { target: { value: '10' } });
    expect(input.value).toBe('10');
  });

  it('submit button is enabled when input has value', () => {
    render(<GameEngine />);
    const input = screen.getByLabelText(/Your Answer/);
    const submitButton = screen.getByText(/Submit/);

    expect(submitButton).toBeDisabled();

    fireEvent.change(input, { target: { value: '5' } });
    expect(submitButton).not.toBeDisabled();
  });

  it('displays feedback after answer submission', async () => {
    render(<GameEngine />);
    const input = screen.getByLabelText(/Your Answer/);
    const submitButton = screen.getByText(/Submit/);

    fireEvent.change(input, { target: { value: '999' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Try again!/)).toBeInTheDocument();
    });
  });

  it('displays scoreboard with initial values', () => {
    render(<GameEngine />);
    expect(screen.getByText(/Score:/)).toBeInTheDocument();
    expect(screen.getByText(/Accuracy:/)).toBeInTheDocument();
  });

  it('displays gorilla character', () => {
    render(<GameEngine />);
    expect(screen.getByText(/You can do it!/)).toBeInTheDocument();
  });

  it('has mute button', () => {
    render(<GameEngine />);
    const muteButton = screen.getByLabelText(/Mute sounds|Unmute sounds/);
    expect(muteButton).toBeInTheDocument();
  });
});
