import { useState, useCallback } from 'react';
import { Phase, PhaseStatus } from '../types/job';

export interface PhaseInfo {
  phase: Phase | null;
  status: PhaseStatus;
  description: string;
  timestamp: string | null;
}

export function usePhase() {
  const [phaseInfo, setPhaseInfo] = useState<PhaseInfo>({
    phase: null,
    status: PhaseStatus.Pending,
    description: '',
    timestamp: null,
  });

  const updatePhase = useCallback((data: {
    phase?: string;
    status?: string;
    description?: string;
    timestamp?: string;
  }) => {
    setPhaseInfo(prev => ({
      phase: data.phase ? (data.phase as Phase) : prev.phase,
      status: data.status ? (data.status as PhaseStatus) : prev.status,
      description: data.description !== undefined ? data.description : prev.description,
      timestamp: data.timestamp !== undefined ? data.timestamp : prev.timestamp,
    }));
  }, []);

  const resetPhase = useCallback(() => {
    setPhaseInfo({
      phase: null,
      status: PhaseStatus.Pending,
      description: '',
      timestamp: null,
    });
  }, []);

  return {
    phaseInfo,
    updatePhase,
    resetPhase,
  };
}
