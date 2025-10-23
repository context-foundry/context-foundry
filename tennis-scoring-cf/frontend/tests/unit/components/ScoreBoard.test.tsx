import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScoreBoard } from '@/components/scoring/ScoreBoard';
import type { MatchDetail } from '@/types/match';

describe('ScoreBoard Component', () => {
  const mockMatch: MatchDetail = {
    id: 1,
    createdBy: 1,
    player1Name: 'Roger Federer',
    player2Name: 'Rafael Nadal',
    matchType: 'singles',
    format: 'best_of_3',
    status: 'in_progress',
    createdAt: '2025-01-20T00:00:00Z',
    updatedAt: '2025-01-20T00:00:00Z',
    sets: [
      {
        id: 1,
        matchId: 1,
        setNumber: 1,
        player1Games: 6,
        player2Games: 4,
        winner: 1,
      },
    ],
    currentSet: {
      id: 2,
      matchId: 1,
      setNumber: 2,
      player1Games: 3,
      player2Games: 2,
    },
    currentGame: {
      id: 1,
      setId: 2,
      gameNumber: 6,
      server: 1,
      player1Points: 2,
      player2Points: 1,
    },
  };

  it('renders score board', () => {
    render(<ScoreBoard match={mockMatch} />);
    expect(screen.getByText('Score')).toBeInTheDocument();
  });

  it('displays LIVE indicator for in-progress matches', () => {
    render(<ScoreBoard match={mockMatch} />);
    expect(screen.getByText('LIVE')).toBeInTheDocument();
  });

  it('displays player names', () => {
    render(<ScoreBoard match={mockMatch} />);
    expect(screen.getByText('Roger Federer')).toBeInTheDocument();
    expect(screen.getByText('Rafael Nadal')).toBeInTheDocument();
  });

  // Add more tests as needed during testing phase
});
