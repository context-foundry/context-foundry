import React from 'react';
import { motion } from 'framer-motion';
import { Phase, PhaseStatus } from '../types/job';

interface PhasePipelineProps {
  currentPhase: Phase | null;
  status: PhaseStatus;
  description: string;
}

const PHASES: Phase[] = [Phase.Scout, Phase.Architect, Phase.Builder, Phase.Test, Phase.Deploy];

const PHASE_ICONS: Record<Phase, string> = {
  [Phase.Scout]: '🔍',
  [Phase.Architect]: '📐',
  [Phase.Builder]: '🔨',
  [Phase.Test]: '🧪',
  [Phase.Deploy]: '🚀',
};

export default function PhasePipeline({ currentPhase, status, description }: PhasePipelineProps) {
  const getPhaseStatus = (phase: Phase): PhaseStatus => {
    if (!currentPhase) return PhaseStatus.Pending;

    const currentIndex = PHASES.indexOf(currentPhase);
    const phaseIndex = PHASES.indexOf(phase);

    if (phaseIndex < currentIndex) return PhaseStatus.Completed;
    if (phaseIndex === currentIndex) return status;
    return PhaseStatus.Pending;
  };

  const getPhaseColor = (phaseStatus: PhaseStatus): string => {
    switch (phaseStatus) {
      case PhaseStatus.Completed:
        return 'bg-green-500';
      case PhaseStatus.Active:
        return 'bg-cyan-500';
      case PhaseStatus.Failed:
        return 'bg-red-500';
      case PhaseStatus.Pending:
      default:
        return 'bg-gray-600';
    }
  };

  const getConnectorColor = (fromPhase: Phase): string => {
    const fromStatus = getPhaseStatus(fromPhase);
    return fromStatus === PhaseStatus.Completed ? 'bg-green-500' : 'bg-gray-700';
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4 text-gray-100">Build Pipeline</h2>

      {/* Desktop/Tablet: Horizontal Layout */}
      <div className="hidden md:flex items-center justify-between">
        {PHASES.map((phase, index) => {
          const phaseStatus = getPhaseStatus(phase);
          const isActive = phaseStatus === PhaseStatus.Active;

          return (
            <React.Fragment key={phase}>
              {/* Phase Node */}
              <div className="flex flex-col items-center gap-2 flex-1">
                <motion.div
                  className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl ${getPhaseColor(phaseStatus)} relative`}
                  animate={isActive ? {
                    scale: [1, 1.1, 1],
                    boxShadow: [
                      '0 0 0 0 rgba(6, 182, 212, 0)',
                      '0 0 0 10px rgba(6, 182, 212, 0.3)',
                      '0 0 0 0 rgba(6, 182, 212, 0)',
                    ],
                  } : {}}
                  transition={isActive ? {
                    duration: 2,
                    repeat: Infinity,
                    ease: 'easeInOut',
                  } : {}}
                >
                  {phaseStatus === PhaseStatus.Completed && (
                    <span className="text-white">✓</span>
                  )}
                  {phaseStatus === PhaseStatus.Failed && (
                    <span className="text-white">✗</span>
                  )}
                  {(phaseStatus === PhaseStatus.Pending || phaseStatus === PhaseStatus.Active) && (
                    <span>{PHASE_ICONS[phase]}</span>
                  )}
                </motion.div>

                <div className="text-center">
                  <div className={`text-sm font-medium ${isActive ? 'text-cyan-400' : 'text-gray-400'}`}>
                    {phase}
                  </div>
                  <div className="text-xs text-gray-500">
                    {phaseStatus === PhaseStatus.Completed && 'Complete'}
                    {phaseStatus === PhaseStatus.Active && 'In Progress'}
                    {phaseStatus === PhaseStatus.Failed && 'Failed'}
                    {phaseStatus === PhaseStatus.Pending && 'Pending'}
                  </div>
                </div>
              </div>

              {/* Connector */}
              {index < PHASES.length - 1 && (
                <div className={`h-1 flex-1 ${getConnectorColor(phase)}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Mobile: Vertical Layout */}
      <div className="md:hidden space-y-4">
        {PHASES.map((phase) => {
          const phaseStatus = getPhaseStatus(phase);
          const isActive = phaseStatus === PhaseStatus.Active;

          return (
            <div key={phase} className="flex items-center gap-3">
              <motion.div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-xl ${getPhaseColor(phaseStatus)}`}
                animate={isActive ? {
                  scale: [1, 1.1, 1],
                } : {}}
                transition={isActive ? {
                  duration: 2,
                  repeat: Infinity,
                } : {}}
              >
                {phaseStatus === PhaseStatus.Completed && <span className="text-white">✓</span>}
                {phaseStatus === PhaseStatus.Failed && <span className="text-white">✗</span>}
                {(phaseStatus === PhaseStatus.Pending || phaseStatus === PhaseStatus.Active) && (
                  <span>{PHASE_ICONS[phase]}</span>
                )}
              </motion.div>

              <div className="flex-1">
                <div className={`font-medium ${isActive ? 'text-cyan-400' : 'text-gray-400'}`}>
                  {phase}
                </div>
                <div className="text-xs text-gray-500">
                  {phaseStatus === PhaseStatus.Completed && 'Complete'}
                  {phaseStatus === PhaseStatus.Active && 'In Progress'}
                  {phaseStatus === PhaseStatus.Failed && 'Failed'}
                  {phaseStatus === PhaseStatus.Pending && 'Pending'}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Current Phase Description */}
      {description && (
        <div className="mt-4 p-3 bg-gray-800 rounded-lg border border-gray-700">
          <p className="text-sm text-gray-300">{description}</p>
        </div>
      )}
    </div>
  );
}
