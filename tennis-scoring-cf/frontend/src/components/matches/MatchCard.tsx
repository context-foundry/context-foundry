import React from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';
import { Match } from '@/types/match';
import { formatDate, getMatchStatusColor, getMatchStatusText, getPlayerNames } from '@/lib/utils';

export interface MatchCardProps {
  match: Match;
}

export function MatchCard({ match }: MatchCardProps) {
  const { team1, team2 } = getPlayerNames(match);
  const statusColor = getMatchStatusColor(match.status);
  const statusText = getMatchStatusText(match.status);

  return (
    <Link href={`/matches/${match.id}`}>
      <Card hover className="transition-all">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-1 text-xs font-medium rounded ${statusColor}`}>
                {statusText}
              </span>
              {match.matchType === 'doubles' && (
                <span className="px-2 py-1 text-xs font-medium rounded bg-purple-100 text-purple-800">
                  Doubles
                </span>
              )}
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{team1}</span>
                {match.winner === 1 && (
                  <span className="text-green-600 font-bold ml-2">W</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{team2}</span>
                {match.winner === 2 && (
                  <span className="text-green-600 font-bold ml-2">W</span>
                )}
              </div>
            </div>

            {match.location && (
              <p className="mt-2 text-sm text-gray-500">
                <svg className="inline w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {match.location}
              </p>
            )}
          </div>

          <div className="text-right">
            {match.scheduledAt && (
              <p className="text-sm text-gray-500">
                {formatDate(match.scheduledAt)}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              {match.format === 'best_of_3' ? 'Best of 3' : 'Best of 5'}
            </p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
