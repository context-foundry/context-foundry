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
    setPhaseInfo(prev => {
      // Normalize status values from backend to PhaseStatus enum
      let normalizedStatus = prev.status;
      if (data.status) {
        // Convert backend status strings to PhaseStatus enum
        const lowerStatus = data.status.toLowerCase();
        if (lowerStatus === 'starting' || lowerStatus === 'in_progress' ||
            lowerStatus === 'building' || lowerStatus === 'running' || lowerStatus === 'active') {
          normalizedStatus = PhaseStatus.Active;
        } else if (lowerStatus === 'completed' || lowerStatus === 'complete') {
          normalizedStatus = PhaseStatus.Completed;
        } else if (lowerStatus === 'failed') {
          normalizedStatus = PhaseStatus.Failed;
        } else {
          normalizedStatus = data.status as PhaseStatus;
        }
      }

      return {
        phase: data.phase ? (data.phase as Phase) : prev.phase,
        status: normalizedStatus,
        description: data.description !== undefined ? data.description : prev.description,
        timestamp: data.timestamp !== undefined ? data.timestamp : prev.timestamp,
      };
    });
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
