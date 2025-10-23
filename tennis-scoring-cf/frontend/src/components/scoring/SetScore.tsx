import React from 'react';
import { Set } from '@/types/match';

export interface SetScoreProps {
  sets: Set[];
  player1Name: string;
  player2Name: string;
  winnerId?: 1 | 2;
}

export function SetScore({ sets, player1Name, player2Name, winnerId }: SetScoreProps) {
  return (
    <div className="bg-white rounded-lg p-6">
      <h3 className="text-sm font-medium text-gray-500 mb-4">Sets</h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-gray-200">
              <th className="text-left py-2 px-2 font-medium text-gray-700 min-w-[120px]">
                Player
              </th>
              {sets.map((set) => (
                <th
                  key={set.id}
                  className="text-center py-2 px-4 font-medium text-gray-700"
                >
                  Set {set.setNumber}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className={winnerId === 1 ? 'bg-green-50' : ''}>
              <td className="py-3 px-2 font-medium text-gray-900">{player1Name}</td>
              {sets.map((set) => (
                <td key={set.id} className="text-center py-3 px-4">
                  <span
                    className={`text-xl font-bold ${
                      set.winner === 1 ? 'text-green-600' : 'text-gray-700'
                    }`}
                  >
                    {set.player1Games}
                  </span>
                  {set.tiebreakScore && (
                    <sup className="text-sm ml-1 text-gray-500">
                      {set.tiebreakScore.player1}
                    </sup>
                  )}
                </td>
              ))}
            </tr>
            <tr className={winnerId === 2 ? 'bg-green-50' : ''}>
              <td className="py-3 px-2 font-medium text-gray-900">{player2Name}</td>
              {sets.map((set) => (
                <td key={set.id} className="text-center py-3 px-4">
                  <span
                    className={`text-xl font-bold ${
                      set.winner === 2 ? 'text-green-600' : 'text-gray-700'
                    }`}
                  >
                    {set.player2Games}
                  </span>
                  {set.tiebreakScore && (
                    <sup className="text-sm ml-1 text-gray-500">
                      {set.tiebreakScore.player2}
                    </sup>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
