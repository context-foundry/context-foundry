/**
 * Sidekick Chat Store
 *
 * Manages the AI chat assistant conversation.
 */

import { create } from 'zustand';
import * as api from '../api/client';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SidekickState {
  // Data
  messages: ChatMessage[];
  lastResponse: string | null;

  // UI State
  isOpen: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  sendMessage: (message: string) => Promise<void>;
  openModal: () => void;
  closeModal: () => void;
  clearHistory: () => void;
}

export const useSidekickStore = create<SidekickState>((set, get) => ({
  // Initial state
  messages: [],
  lastResponse: null,
  isOpen: false,
  isLoading: false,
  error: null,

  sendMessage: async (message: string) => {
    if (!message.trim()) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date(),
    };

    // Add user message immediately
    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true,
      error: null,
    }));

    try {
      // Build history for API (last 10 exchanges)
      const history = get()
        .messages.slice(-20)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      // Send to API
      const response = await api.sendChatMessage('', message, history);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response,
        timestamp: new Date(),
      };

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        lastResponse: response,
        isLoading: false,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';

      // Add error as assistant message
      const errorResponse: ChatMessage = {
        role: 'assistant',
        content: "I'm having a bit of a glitch moment. Please try again.",
        timestamp: new Date(),
      };

      set((state) => ({
        messages: [...state.messages, errorResponse],
        error: errorMessage,
        isLoading: false,
      }));
    }
  },

  openModal: () => {
    set({ isOpen: true });
  },

  closeModal: () => {
    set({ isOpen: false });
  },

  clearHistory: () => {
    set({ messages: [], lastResponse: null, error: null });
  },
}));

// Selectors
export const useRecentMessages = (count = 5) => {
  return useSidekickStore((state) => state.messages.slice(-count * 2));
};
