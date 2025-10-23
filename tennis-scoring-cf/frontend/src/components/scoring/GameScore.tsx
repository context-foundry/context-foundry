import React from 'react';
import { Game } from '@/types/match';
import { formatScore } from '@/lib/utils';

export interface GameScoreProps {
  game: Game;
  player1Name: string;
  player2Name: string;
}

export function GameScore({ game, player1Name, player2Name }: GameScoreProps) {
  const scoreDisplay = formatScore(game.player1Points, game.player2Points);
  const isServing1 = game.server === 1;
  const isServing2 = game.server === 2;

  return (
    <div className="bg-white rounded-lg p-6 border-2 border-blue-200">
      <h3 className="text-sm font-medium text-gray-500 mb-4">Current Game</h3>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isServing1 && (
              <svg className="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <circle cx="10" cy="10" r="8" />
              </svg>
            )}
            <span className="font-semibold text-lg text-gray-900">{player1Name}</span>
          </div>
          <span className="text-3xl font-bold text-blue-600">
            {scoreDisplay === 'Deuce' || scoreDisplay === 'Ad In' || scoreDisplay === 'Ad Out'
              ? ''
              : scoreDisplay.split('-')[0]}
          </span>
        </div>

        {(scoreDisplay === 'Deuce' || scoreDisplay === 'Ad In' || scoreDisplay === 'Ad Out') && (
          <div className="text-center py-2">
            <span className="text-2xl font-bold text-orange-600">{scoreDisplay}</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isServing2 && (
              <svg className="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <circle cx="10" cy="10" r="8" />
              </svg>
            )}
            <span className="font-semibold text-lg text-gray-900">{player2Name}</span>
          </div>
          <span className="text-3xl font-bold text-blue-600">
            {scoreDisplay === 'Deuce' || scoreDisplay === 'Ad In' || scoreDisplay === 'Ad Out'
              ? ''
              : scoreDisplay.split('-')[1]}
          </span>
        </div>
      </div>
    </div>
  );
}
