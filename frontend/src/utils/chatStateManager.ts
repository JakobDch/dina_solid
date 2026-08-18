import type { ChatSessionData } from '../types';

const CHAT_STATE_KEY = 'dina_esg_chat_state';

interface ChatState {
  currentSession?: ChatSessionData;
  lastUpdated: string;
}

export class ChatStateManager {
  /**
   * Save current chat state to localStorage
   */
  static saveState(session: ChatSessionData): void {
    try {
      const state: ChatState = {
        currentSession: session,
        lastUpdated: new Date().toISOString()
      };
      localStorage.setItem(CHAT_STATE_KEY, JSON.stringify(state));
    } catch (error) {
      console.warn('Failed to save chat state:', error);
    }
  }

  /**
   * Load chat state from localStorage
   */
  static loadState(): ChatSessionData | null {
    try {
      const stored = localStorage.getItem(CHAT_STATE_KEY);
      if (!stored) return null;

      const state: ChatState = JSON.parse(stored);

      // Check if state is not too old (24 hours)
      const lastUpdated = new Date(state.lastUpdated);
      const now = new Date();
      const hoursDiff = (now.getTime() - lastUpdated.getTime()) / (1000 * 60 * 60);

      if (hoursDiff > 24) {
        this.clearState();
        return null;
      }

      return state.currentSession || null;
    } catch (error) {
      console.warn('Failed to load chat state:', error);
      this.clearState();
      return null;
    }
  }

  /**
   * Clear stored chat state
   */
  static clearState(): void {
    try {
      localStorage.removeItem(CHAT_STATE_KEY);
    } catch (error) {
      console.warn('Failed to clear chat state:', error);
    }
  }

  /**
   * Update specific parts of the chat session
   */
  static updateSession(updates: Partial<ChatSessionData>): void {
    const currentState = this.loadState();
    if (currentState) {
      const updatedSession = { ...currentState, ...updates };
      this.saveState(updatedSession);
    }
  }

  /**
   * Save session (alias for saveState for compatibility)
   */
  static saveSession(session: ChatSessionData): void {
    this.saveState(session);
  }

  /**
   * Check if there's a valid saved state
   */
  static hasValidState(): boolean {
    return this.loadState() !== null;
  }

  /**
   * Get state age in hours
   */
  static getStateAge(): number | null {
    try {
      const stored = localStorage.getItem(CHAT_STATE_KEY);
      if (!stored) return null;

      const state: ChatState = JSON.parse(stored);
      const lastUpdated = new Date(state.lastUpdated);
      const now = new Date();
      return (now.getTime() - lastUpdated.getTime()) / (1000 * 60 * 60);
    } catch (error) {
      return null;
    }
  }
}