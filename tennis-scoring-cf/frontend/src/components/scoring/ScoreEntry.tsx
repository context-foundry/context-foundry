'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { useMatchScore } from '@/hooks/useMatches';
import { getPlayerNames } from '@/lib/utils';
import type { MatchDetail } from '@/types/match';

export interface ScoreEntryProps {
  match: MatchDetail;
  onScoreUpdate: () => void;
}

export function ScoreEntry({ match, onScoreUpdate }: ScoreEntryProps) {
  const { startMatch, recordPoint, completeMatch, loading } = useMatchScore(match.id);
  const { team1, team2 } = getPlayerNames(match);
  const [showCompleteModal, setShowCompleteModal] = useState(false);

  const handleStartMatch = async () => {
    try {
      await startMatch();
      onScoreUpdate();
    } catch (error) {
      console.error('Failed to start match:', error);
    }
  };

  const handleRecordPoint = async (winner: 1 | 2) => {
    try {
      await recordPoint(winner);
      onScoreUpdate();
    } catch (error) {
      console.error('Failed to record point:', error);
    }
  };

  const handleCompleteMatch = async () => {
    try {
      await completeMatch();
      setShowCompleteModal(false);
      onScoreUpdate();
    } catch (error) {
      console.error('Failed to complete match:', error);
    }
  };

  if (match.status === 'scheduled') {
    return (
      <Card className="bg-blue-50">
        <div className="text-center py-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Match Not Started
          </h3>
          <Button onClick={handleStartMatch} loading={loading} size="lg">
            Start Match
          </Button>
        </div>
      </Card>
    );
  }

  if (match.status === 'completed') {
    return (
      <Card className="bg-green-50">
        <div className="text-center py-8">
          <h3 className="text-lg font-semibold text-green-800 mb-2">
            Match Completed
          </h3>
          <p className="text-gray-600">
            Winner: {match.winner === 1 ? team1 : team2}
          </p>
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card className="bg-gradient-to-br from-green-50 to-emerald-50">
        <div className="space-y-6">
          <h3 className="text-xl font-semibold text-gray-900 text-center">
            Record Point
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Button
              onClick={() => handleRecordPoint(1)}
              loading={loading}
              size="lg"
              className="h-24 text-xl"
            >
              {team1}
              <br />
              <span className="text-sm font-normal">Point</span>
            </Button>

            <Button
              onClick={() => handleRecordPoint(2)}
              loading={loading}
              size="lg"
              className="h-24 text-xl"
            >
              {team2}
              <br />
              <span className="text-sm font-normal">Point</span>
            </Button>
          </div>

          <div className="pt-4 border-t border-gray-200">
            <Button
              onClick={() => setShowCompleteModal(true)}
              variant="outline"
              fullWidth
            >
              Complete Match
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        isOpen={showCompleteModal}
        onClose={() => setShowCompleteModal(false)}
        title="Complete Match"
      >
        <div className="space-y-4">
          <p className="text-gray-700">
            Are you sure you want to complete this match? This action cannot be undone.
          </p>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => setShowCompleteModal(false)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleCompleteMatch}
              loading={loading}
            >
              Complete Match
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
