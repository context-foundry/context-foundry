import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MatchCard } from '@/components/matches/MatchCard';
import type { Match } from '@/types/match';

describe('MatchCard Component', () => {
  const mockMatch: Match = {
    id: 1,
    createdBy: 1,
    player1Name: 'John Doe',
    player2Name: 'Jane Smith',
    matchType: 'singles',
    format: 'best_of_3',
    status: 'scheduled',
    location: 'Court 1',
    createdAt: '2025-01-20T00:00:00Z',
    updatedAt: '2025-01-20T00:00:00Z',
  };

  it('renders match card', () => {
    render(<MatchCard match={mockMatch} />);
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
  });

  it('displays match location', () => {
    render(<MatchCard match={mockMatch} />);
    expect(screen.getByText('Court 1')).toBeInTheDocument();
  });

  it('shows match status', () => {
    render(<MatchCard match={mockMatch} />);
    expect(screen.getByText('Scheduled')).toBeInTheDocument();
  });

  // Add more tests as needed during testing phase
});
