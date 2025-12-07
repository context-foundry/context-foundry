/**
 * Approvals Store
 *
 * Manages pending HITL approvals and approval workflow.
 */

import { create } from 'zustand';
import type { PendingApproval } from '../types';
import * as api from '../api/client';

interface ApprovalsState {
  // Data
  pendingApprovals: PendingApproval[];
  selectedApprovalId: string | null;

  // UI State
  isLoading: boolean;
  error: string | null;
  showModal: boolean;

  // Actions
  fetchApprovals: () => Promise<void>;
  selectApproval: (approvalId: string | null) => void;
  approve: (approvalId: string) => Promise<void>;
  deny: (approvalId: string, reason?: string) => Promise<void>;
  resumePipeline: (jobId: string) => Promise<void>;
  openModal: () => void;
  closeModal: () => void;
}

export const useApprovalsStore = create<ApprovalsState>((set, get) => ({
  // Initial state
  pendingApprovals: [],
  selectedApprovalId: null,
  isLoading: false,
  error: null,
  showModal: false,

  fetchApprovals: async () => {
    set({ isLoading: true, error: null });

    try {
      const approvals = await api.getPendingApprovals();
      set({ pendingApprovals: approvals, isLoading: false });

      // Auto-open modal if there are pending approvals
      if (approvals.length > 0 && !get().showModal) {
        set({ showModal: true, selectedApprovalId: approvals[0].id });
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch approvals',
        isLoading: false,
      });
    }
  },

  selectApproval: (approvalId) => {
    set({ selectedApprovalId: approvalId });
  },

  approve: async (approvalId) => {
    set({ isLoading: true, error: null });

    try {
      await api.approveAction(approvalId);
      // Remove from pending list
      set((state) => ({
        pendingApprovals: state.pendingApprovals.filter((a) => a.id !== approvalId),
        isLoading: false,
        selectedApprovalId: null,
      }));

      // Close modal if no more approvals
      if (get().pendingApprovals.length === 0) {
        set({ showModal: false });
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to approve',
        isLoading: false,
      });
    }
  },

  deny: async (approvalId, reason) => {
    set({ isLoading: true, error: null });

    try {
      await api.denyAction(approvalId, reason);
      // Remove from pending list
      set((state) => ({
        pendingApprovals: state.pendingApprovals.filter((a) => a.id !== approvalId),
        isLoading: false,
        selectedApprovalId: null,
      }));

      // Close modal if no more approvals
      if (get().pendingApprovals.length === 0) {
        set({ showModal: false });
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to deny',
        isLoading: false,
      });
    }
  },

  resumePipeline: async (jobId) => {
    set({ isLoading: true, error: null });

    try {
      await api.resumePipeline(jobId);
      set({ isLoading: false });
      // Refresh approvals
      get().fetchApprovals();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to resume pipeline',
        isLoading: false,
      });
    }
  },

  openModal: () => {
    set({ showModal: true });
  },

  closeModal: () => {
    set({ showModal: false, selectedApprovalId: null });
  },
}));

// Selectors
export const useSelectedApproval = () => {
  const approvals = useApprovalsStore((state) => state.pendingApprovals);
  const selectedId = useApprovalsStore((state) => state.selectedApprovalId);
  return approvals.find((a) => a.id === selectedId) ?? null;
};

export const useApprovalCount = () => {
  return useApprovalsStore((state) => state.pendingApprovals.length);
};
