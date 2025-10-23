'use client';

import React from 'react';
import { MatchDetail as MatchDetailType, Set } from '@/types/match';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { getPlayerNames, formatDateTime } from '@/lib/utils';

export interface MatchDetailProps {
  match: MatchDetailType;
}

export function MatchDetail({ match }: MatchDetailProps) {
  const { team1, team2 } = getPlayerNames(match);

  return (
    <div className="space-y-6">
      {/* Match Info */}
      <Card>
        <CardHeader>
          <CardTitle>Match Information</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">Type</dt>
              <dd className="mt-1 text-sm text-gray-900 capitalize">{match.matchType}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Format</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {match.format === 'best_of_3' ? 'Best of 3 Sets' : 'Best of 5 Sets'}
              </dd>
            </div>
            {match.location && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Location</dt>
                <dd className="mt-1 text-sm text-gray-900">{match.location}</dd>
              </div>
            )}
            {match.scheduledAt && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Scheduled</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDateTime(match.scheduledAt)}
                </dd>
              </div>
            )}
            {match.startedAt && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Started</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDateTime(match.startedAt)}
                </dd>
              </div>
            )}
            {match.completedAt && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Completed</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDateTime(match.completedAt)}
                </dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Set Scores */}
      {match.sets && match.sets.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Set Scores</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-4 font-medium text-gray-700">Player</th>
                    {match.sets.map((set) => (
                      <th key={set.id} className="text-center py-2 px-4 font-medium text-gray-700">
                        Set {set.setNumber}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className={match.winner === 1 ? 'bg-green-50' : ''}>
                    <td className="py-2 px-4 font-medium">{team1}</td>
                    {match.sets.map((set) => (
                      <td key={set.id} className="text-center py-2 px-4">
                        <span className={set.winner === 1 ? 'font-bold text-green-600' : ''}>
                          {set.player1Games}
                          {set.tiebreakScore && (
                            <sup className="text-xs ml-0.5">{set.tiebreakScore.player1}</sup>
                          )}
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr className={match.winner === 2 ? 'bg-green-50' : ''}>
                    <td className="py-2 px-4 font-medium">{team2}</td>
                    {match.sets.map((set) => (
                      <td key={set.id} className="text-center py-2 px-4">
                        <span className={set.winner === 2 ? 'font-bold text-green-600' : ''}>
                          {set.player2Games}
                          {set.tiebreakScore && (
                            <sup className="text-xs ml-0.5">{set.tiebreakScore.player2}</sup>
                          )}
                        </span>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
