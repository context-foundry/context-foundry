import { useJobsStore } from '../../stores/jobs';
import type { Job, Phase, TaskStatus } from '../../types';

interface PhaseTimelineProps {
  job: Job;
}

// Default phase order (fallback when expected_phases not available)
const DEFAULT_PHASE_ORDER: Phase[] = [
  'scout',
  'architect',
  'builder',
  'test',
  'screenshot',
  'documentation',
  'deploy',
  'feedback',
];

const STATUS_CLASSES: Record<TaskStatus, string> = {
  created: 'phase-created',
  queued: 'phase-queued',
  running: 'phase-running',
  succeeded: 'phase-succeeded',
  failed: 'phase-failed',
  cancelled: 'phase-cancelled',
  timed_out: 'phase-failed',
};

export function PhaseTimeline({ job }: PhaseTimelineProps) {
  const { selectedPhase, selectPhase } = useJobsStore();

  // Create a map of phase -> task for quick lookup
  const phaseMap = new Map((job.phases || []).map((task) => [task.phase, task]));

  // Use expected_phases from job (Issue #191), fall back to default
  const phasesToShow = (job.expected_phases as Phase[]) || DEFAULT_PHASE_ORDER;

  return (
    <div className="phase-timeline">
      {phasesToShow.map((phase) => {
        const task = phaseMap.get(phase);
        const status = task?.status ?? 'created';
        const isActive = phase === job.current_phase;
        const isSelected = phase === selectedPhase;

        return (
          <button
            key={phase}
            className={`phase-item ${STATUS_CLASSES[status]} ${isActive ? 'active' : ''} ${isSelected ? 'selected' : ''}`}
            onClick={() => selectPhase(phase)}
          >
            <span className="phase-icon">{getPhaseIcon(phase, status)}</span>
            <span className="phase-name">{phase}</span>
          </button>
        );
      })}
    </div>
  );
}

function getPhaseIcon(_phase: Phase, status: TaskStatus): string {
  if (status === 'running') return '...';
  if (status === 'succeeded') return '✓';
  if (status === 'failed' || status === 'timed_out') return '✗';
  if (status === 'cancelled') return '—';

  // Default icons by phase - removed per user request
  // const icons: Record<Phase, string> = {
  //   scout: '🔍',
  //   architect: '📐',
  //   builder: '🔨',
  //   test: '🧪',
  //   screenshot: '📸',
  //   documentation: '📝',
  //   deploy: '🚀',
  //   feedback: '💬',
  // };

  // return icons[phase] ?? '○';
  return '';
}
