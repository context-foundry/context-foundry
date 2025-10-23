'use client';

import React from 'react';
import { MatchDetail, Set, Game } from '@/types/match';
import { Card } from '@/components/ui/Card';
import { getPlayerNames, formatScore } from '@/lib/utils';
import { SetScore } from './SetScore';
import { GameScore } from './GameScore';

export interface ScoreBoardProps {
  match: MatchDetail;
}

export function ScoreBoard({ match }: ScoreBoardProps) {
  const { team1, team2 } = getPlayerNames(match);
  const isLive = match.status === 'in_progress';

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Score</h2>
          {isLive && (
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
              </span>
              <span className="text-sm font-medium text-red-600">LIVE</span>
            </div>
          )}
        </div>

        {/* Current Game Score */}
        {match.currentGame && (
          <GameScore
            game={match.currentGame}
            player1Name={team1}
            player2Name={team2}
          />
        )}

        {/* Set Scores */}
        {match.sets && match.sets.length > 0 && (
          <SetScore
            sets={match.sets}
            player1Name={team1}
            player2Name={team2}
            winnerId={match.winner}
          />
        )}

        {/* Match Status */}
        {match.status === 'completed' && match.winner && (
          <div className="text-center py-4 bg-green-100 rounded-lg">
            <p className="text-lg font-bold text-green-800">
              {match.winner === 1 ? team1 : team2} wins!
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
