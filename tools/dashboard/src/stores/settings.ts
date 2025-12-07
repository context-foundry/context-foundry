/**
 * Settings Store
 *
 * Manages team settings (S3 sync) and daemon configuration.
 * This is where users configure their team's shared pattern bucket.
 */

import { create } from 'zustand';
import type { TeamSettings, DaemonSettings } from '../types';
import * as api from '../api/client';

interface SettingsState {
  // Data
  teamSettings: TeamSettings | null;
  daemonSettings: DaemonSettings | null;

  // UI State
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  successMessage: string | null;
  showSettingsPanel: boolean;
  activeTab: 'team' | 'daemon' | 'about';

  // S3 Test State
  isTestingS3: boolean;
  s3TestResult: { success: boolean; message: string } | null;

  // Actions
  fetchSettings: () => Promise<void>;
  updateTeamSettings: (settings: Partial<TeamSettings>) => Promise<void>;
  testS3Connection: () => Promise<void>;
  openSettings: () => void;
  closeSettings: () => void;
  setActiveTab: (tab: 'team' | 'daemon' | 'about') => void;
  clearMessages: () => void;
}

const DEFAULT_TEAM_SETTINGS: TeamSettings = {
  team_id: null,
  s3_bucket: null,
  s3_prefix: 'shared-patterns/',
  s3_region: 'us-east-1',
  aws_profile: null,
  sync_mode: 'local-only',
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  // Initial state
  teamSettings: null,
  daemonSettings: null,
  isLoading: false,
  isSaving: false,
  error: null,
  successMessage: null,
  showSettingsPanel: false,
  activeTab: 'team',
  isTestingS3: false,
  s3TestResult: null,

  fetchSettings: async () => {
    set({ isLoading: true, error: null });

    try {
      const [teamSettings, daemonSettings] = await Promise.all([
        api.getTeamSettings().catch(() => DEFAULT_TEAM_SETTINGS),
        api.getDaemonSettings().catch(() => null),
      ]);

      set({
        teamSettings,
        daemonSettings,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch settings',
        isLoading: false,
        teamSettings: DEFAULT_TEAM_SETTINGS,
      });
    }
  },

  updateTeamSettings: async (settings) => {
    set({ isSaving: true, error: null, successMessage: null });

    try {
      await api.updateTeamSettings(settings);

      // Update local state
      set((state) => ({
        teamSettings: state.teamSettings
          ? { ...state.teamSettings, ...settings }
          : { ...DEFAULT_TEAM_SETTINGS, ...settings },
        isSaving: false,
        successMessage: 'Settings saved successfully',
        s3TestResult: null, // Clear test result on save
      }));

      // Clear success message after 3 seconds
      setTimeout(() => {
        set({ successMessage: null });
      }, 3000);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to save settings',
        isSaving: false,
      });
    }
  },

  testS3Connection: async () => {
    set({ isTestingS3: true, s3TestResult: null, error: null });

    try {
      const result = await api.testS3Connection();
      set({ s3TestResult: result, isTestingS3: false });
    } catch (error) {
      set({
        s3TestResult: {
          success: false,
          message: error instanceof Error ? error.message : 'Connection test failed',
        },
        isTestingS3: false,
      });
    }
  },

  openSettings: () => {
    set({ showSettingsPanel: true });
    get().fetchSettings();
  },

  closeSettings: () => {
    set({ showSettingsPanel: false, error: null, successMessage: null, s3TestResult: null });
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab, error: null, successMessage: null });
  },

  clearMessages: () => {
    set({ error: null, successMessage: null });
  },
}));

// Selectors
export const useSyncMode = () => {
  return useSettingsStore((state) => state.teamSettings?.sync_mode ?? 'local-only');
};

export const useTeamId = () => {
  return useSettingsStore((state) => state.teamSettings?.team_id ?? null);
};

export const useIsTeamConfigured = () => {
  const settings = useSettingsStore((state) => state.teamSettings);
  return Boolean(settings?.team_id && settings?.s3_bucket);
};
