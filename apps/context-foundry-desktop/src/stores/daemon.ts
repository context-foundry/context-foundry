/**
 * Daemon State Store
 *
 * Manages the daemon connection status and provides actions
 * for controlling the daemon.
 */

import { create } from 'zustand'
import { listen } from '@tauri-apps/api/event'
import type { DaemonStatus } from '../types'
import * as api from '../api/daemon'

interface DaemonState {
  // State
  status: DaemonStatus | null
  isLoading: boolean
  error: string | null

  // Actions
  checkStatus: () => Promise<void>
  startDaemon: () => Promise<void>
  stopDaemon: () => Promise<void>
  restartDaemon: () => Promise<void>
  clearError: () => void

  // Event listener setup
  setupEventListeners: () => Promise<() => void>
}

export const useDaemonStore = create<DaemonState>((set) => ({
  // Initial state
  status: null,
  isLoading: false,
  error: null,

  // Check daemon status
  checkStatus: async () => {
    set({ isLoading: true, error: null })
    try {
      const status = await api.checkDaemonStatus()
      set({ status, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to check daemon status',
        isLoading: false,
      })
    }
  },

  // Start daemon
  startDaemon: async () => {
    set({ isLoading: true, error: null })
    try {
      const status = await api.startDaemon()
      set({ status, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to start daemon',
        isLoading: false,
      })
    }
  },

  // Stop daemon
  stopDaemon: async () => {
    set({ isLoading: true, error: null })
    try {
      await api.stopDaemon()
      set({
        status: { running: false, port: 8421 },
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to stop daemon',
        isLoading: false,
      })
    }
  },

  // Restart daemon
  restartDaemon: async () => {
    set({ isLoading: true, error: null })
    try {
      const status = await api.restartDaemon()
      set({ status, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to restart daemon',
        isLoading: false,
      })
    }
  },

  // Clear error
  clearError: () => set({ error: null }),

  // Setup Tauri event listeners for daemon status updates
  setupEventListeners: async () => {
    const unlistenStatus = await listen<DaemonStatus>('daemon-status', (event) => {
      set({ status: event.payload, error: null })
    })

    const unlistenError = await listen<string>('daemon-error', (event) => {
      set({ error: event.payload })
    })

    return () => {
      unlistenStatus()
      unlistenError()
    }
  },
}))
