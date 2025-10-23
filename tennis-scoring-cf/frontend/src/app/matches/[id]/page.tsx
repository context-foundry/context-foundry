'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useMatch } from '@/hooks/useMatches';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAuth } from '@/hooks/useAuth';
import { socketClient } from '@/lib/socket';
import { ScoreBoard } from '@/components/scoring/ScoreBoard';
import { ScoreEntry } from '@/components/scoring/ScoreEntry';
import { MatchDetail } from '@/components/matches/MatchDetail';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

export default function MatchDetailPage() {
  const params = useParams();
  const matchId = parseInt(params.id as string);
  const { match, loading, error, refetch, setMatch } = useMatch(matchId);
  const { joinMatch, leaveMatch } = useWebSocket();
  const { user } = useAuth();
  const [viewerCount, setViewerCount] = useState(0);

  // Join match room and listen for updates
  useEffect(() => {
    if (matchId) {
      joinMatch(matchId);

      // Listen for score updates
      socketClient.onScoreUpdate((data) => {
        console.log('Score update received:', data);
        refetch();
      });

      // Listen for viewer updates
      socketClient.onViewerJoined((data) => {
        setViewerCount((prev) => prev + 1);
      });

      socketClient.onViewerLeft((data) => {
        setViewerCount((prev) => Math.max(0, prev - 1));
      });

      return () => {
        leaveMatch(matchId);
        socketClient.offScoreUpdate();
        socketClient.offViewerJoined();
        socketClient.offViewerLeft();
      };
    }
  }, [matchId, joinMatch, leaveMatch, refetch]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading match...</p>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Match Not Found</h1>
          <p className="text-gray-600 mb-6">{error || 'The match you are looking for does not exist.'}</p>
          <Link href="/">
            <Button>Back to Matches</Button>
          </Link>
        </div>
      </div>
    );
  }

  const isCoach = user?.role === 'coach' || user?.role === 'admin';
  const isMatchOwner = user?.id === match.createdBy;
  const canManageScore = isCoach && isMatchOwner;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <div className="mb-6">
        <Link href="/">
          <Button variant="ghost" size="sm">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Matches
          </Button>
        </Link>
      </div>

      {/* Viewer Count */}
      {match.status === 'in_progress' && (
        <div className="mb-4 text-sm text-gray-600 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          {viewerCount} {viewerCount === 1 ? 'viewer' : 'viewers'} watching
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <ScoreBoard match={match} />
          <MatchDetail match={match} />
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Score Entry (Coaches Only) */}
          {canManageScore && (
            <ScoreEntry match={match} onScoreUpdate={refetch} />
          )}

          {/* Match Actions */}
          {canManageScore && (
            <div className="space-y-2">
              <Link href={`/matches/${match.id}/edit`}>
                <Button variant="outline" fullWidth>
                  Edit Match Details
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
