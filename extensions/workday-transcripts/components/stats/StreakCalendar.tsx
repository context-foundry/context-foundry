'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface StreakCalendarProps {
  dailyReviews: { date: string; count: number }[];
  className?: string;
}

export function StreakCalendar({ dailyReviews, className }: StreakCalendarProps) {
  const calendarData = useMemo(() => {
    const today = new Date();
    const weeks = 12; // Show 12 weeks
    const days: { date: string; count: number; level: number }[] = [];

    // Create map for quick lookup
    const reviewMap = new Map(dailyReviews.map((r) => [r.date, r.count]));

    // Generate last N weeks of dates
    for (let i = weeks * 7 - 1; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      const count = reviewMap.get(dateStr) || 0;

      // Calculate intensity level (0-4)
      let level = 0;
      if (count > 0) {
        if (count >= 50) level = 4;
        else if (count >= 30) level = 3;
        else if (count >= 15) level = 2;
        else level = 1;
      }

      days.push({ date: dateStr, count, level });
    }

    return days;
  }, [dailyReviews]);

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-start gap-1">
        {/* Day labels */}
        <div className="flex flex-col gap-1 text-xs text-muted-foreground pr-2">
          {weekDays.map((day, i) => (
            <div key={day} className="h-3 flex items-center">
              {i % 2 === 1 && day}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="flex gap-1">
          {Array.from({ length: 12 }).map((_, weekIndex) => (
            <div key={weekIndex} className="flex flex-col gap-1">
              {Array.from({ length: 7 }).map((_, dayIndex) => {
                const dataIndex = weekIndex * 7 + dayIndex;
                const day = calendarData[dataIndex];

                if (!day) return <div key={dayIndex} className="w-3 h-3" />;

                return (
                  <div
                    key={dayIndex}
                    className={cn(
                      'w-3 h-3 rounded-sm streak-cell',
                      `streak-cell-${day.level}`
                    )}
                    title={`${day.date}: ${day.count} reviews`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-end gap-1 text-xs text-muted-foreground">
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((level) => (
          <div
            key={level}
            className={cn('w-3 h-3 rounded-sm streak-cell', `streak-cell-${level}`)}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}

export default StreakCalendar;
