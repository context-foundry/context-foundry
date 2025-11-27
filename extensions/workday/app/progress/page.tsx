import { ProgressDashboard } from '@/components/progress/ProgressDashboard';

export const metadata = {
  title: 'Your Progress - WorkWise',
  description: 'Track your learning progress and achievements',
};

export default function ProgressPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <ProgressDashboard />
    </div>
  );
}
