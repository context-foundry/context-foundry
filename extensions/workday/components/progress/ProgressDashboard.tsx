'use client';

import React from 'react';
import { useProgressStats, useProgress } from '@/lib/progress/progress-store';
import { Trophy, Target, Clock, Award, TrendingUp, Zap } from 'lucide-react';
import { AchievementBadge } from './AchievementBadge';
import { MilestoneTracker } from './MilestoneTracker';
import { CompletionChart } from './CompletionChart';

export function ProgressDashboard() {
  const stats = useProgressStats();
  const { progress } = useProgress();

  const statCards = [
    {
      icon: Trophy,
      label: 'Patterns Completed',
      value: stats.totalCompleted,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
    {
      icon: Target,
      label: 'Quizzes Passed',
      value: stats.totalQuizzes,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      icon: Zap,
      label: 'Scenarios Completed',
      value: stats.totalScenarios,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      icon: Clock,
      label: 'Time Spent (hours)',
      value: Math.round(stats.totalTime / 60),
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      icon: TrendingUp,
      label: 'Average Score',
      value: `${stats.averageScore}%`,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-50',
    },
    {
      icon: Award,
      label: 'Achievements',
      value: stats.achievementCount,
      color: 'text-pink-600',
      bgColor: 'bg-pink-50',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Your Progress</h1>
        <p className="text-gray-600">
          Track your learning journey and celebrate your achievements
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                  <Icon className={`h-6 w-6 ${stat.color}`} aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Completion Chart */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Completion Overview
        </h2>
        <CompletionChart
          completed={stats.totalCompleted}
          total={169}
        />
      </div>

      {/* Milestone Tracker */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Milestones</h2>
        <MilestoneTracker currentCount={stats.totalCompleted} />
      </div>

      {/* Achievements */}
      {progress.achievements.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Recent Achievements
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {progress.achievements
              .slice()
              .sort((a, b) => b.unlockedAt - a.unlockedAt)
              .slice(0, 6)
              .map((achievement) => (
                <AchievementBadge
                  key={achievement.id}
                  achievement={achievement}
                  showAnimation={false}
                />
              ))}
          </div>

          {progress.achievements.length > 6 && (
            <p className="mt-4 text-sm text-gray-600 text-center">
              And {progress.achievements.length - 6} more...
            </p>
          )}
        </div>
      )}

      {/* Streak Info */}
      {stats.currentStreak > 0 && (
        <div className="bg-gradient-to-r from-orange-50 to-red-50 rounded-lg border border-orange-200 p-6">
          <div className="flex items-center gap-4">
            <div className="text-4xl">🔥</div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {stats.currentStreak} Day Streak!
              </h3>
              <p className="text-sm text-gray-600">
                Keep it up! Your longest streak is {stats.longestStreak} days.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
