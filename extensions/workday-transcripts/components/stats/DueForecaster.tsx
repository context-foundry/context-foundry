'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ReviewForecast } from '@/types/progress';

interface DueForecasterProps {
  forecast: ReviewForecast[];
  className?: string;
}

export function DueForecaster({ forecast, className }: DueForecasterProps) {
  const chartData = useMemo(() => {
    return forecast.slice(0, 14).map((f) => ({
      date: new Date(f.date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
      reviews: f.reviewCount,
      new: f.newCount,
      total: f.reviewCount + f.newCount,
    }));
  }, [forecast]);

  const todayTotal = forecast[0]
    ? forecast[0].reviewCount + forecast[0].newCount
    : 0;

  if (forecast.length === 0) {
    return (
      <Card className={cn(className)}>
        <CardHeader>
          <CardTitle className="text-lg">Review Forecast</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] flex items-center justify-center text-muted-foreground">
            No forecast data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Review Forecast</CardTitle>
          <div className="text-right">
            <div className="text-2xl font-bold text-primary">{todayTotal}</div>
            <div className="text-xs text-muted-foreground">due today</div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              className="text-xs"
              tick={{ fill: 'currentColor' }}
            />
            <YAxis
              className="text-xs"
              tick={{ fill: 'currentColor' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              }}
            />
            <Bar
              dataKey="reviews"
              fill="hsl(var(--primary))"
              stackId="stack"
              name="Reviews"
            />
            <Bar
              dataKey="new"
              fill="hsl(var(--primary) / 0.5)"
              stackId="stack"
              name="New Cards"
            />
          </BarChart>
        </ResponsiveContainer>
        <div className="flex items-center justify-center gap-4 mt-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-primary" />
            <span>Reviews</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-primary/50" />
            <span>New Cards</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default DueForecaster;
