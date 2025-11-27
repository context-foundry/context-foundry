'use client';

import React, { useState, useEffect } from 'react';
import { Achievement } from '@/types/progress';
import {
  Trophy,
  Award,
  Medal,
  Crown,
  Star,
  Zap,
  Target,
  Rocket,
} from 'lucide-react';

interface AchievementBadgeProps {
  achievement: Achievement;
  showAnimation?: boolean;
}

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  trophy: Trophy,
  award: Award,
  medal: Medal,
  crown: Crown,
  star: Star,
  zap: Zap,
  target: Target,
  rocket: Rocket,
};

export function AchievementBadge({
  achievement,
  showAnimation = true,
}: AchievementBadgeProps) {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (showAnimation) {
      setAnimate(true);
    }
  }, [showAnimation]);

  const Icon = iconMap[achievement.iconName] || Trophy;

  const formatDate = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div
      className={`bg-gradient-to-br from-yellow-50 to-yellow-100 border-2 border-yellow-300 rounded-lg p-4 shadow-sm hover:shadow-md transition-all ${
        animate ? 'animate-bounce-in' : ''
      }`}
      role="article"
      aria-label={`Achievement: ${achievement.name}`}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="flex-shrink-0">
          <div className="p-3 bg-yellow-200 rounded-full">
            <Icon className="h-6 w-6 text-yellow-700" aria-hidden="true" />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 mb-1">{achievement.name}</h3>
          <p className="text-sm text-gray-700 mb-2">{achievement.description}</p>
          <p className="text-xs text-gray-600">
            Unlocked {formatDate(achievement.unlockedAt)}
          </p>

          {/* Metadata */}
          {achievement.metadata && Object.keys(achievement.metadata).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(achievement.metadata).map(([key, value]) => (
                <span
                  key={key}
                  className="inline-block px-2 py-1 bg-yellow-200 text-yellow-800 rounded text-xs"
                >
                  {String(value)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
