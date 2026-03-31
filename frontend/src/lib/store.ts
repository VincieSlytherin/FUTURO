import { create } from "zustand";
import { nanoid } from "nanoid" ;
import type { Message, MemoryUpdate } from "@/types";

// ── Auth store ────────────────────────────────────────────────────────────────

interface AuthState {
  isAuthenticated: boolean;
  setAuthenticated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  setAuthenticated: (v) => set({ isAuthenticated: v }),
}));

// ── Chat store ────────────────────────────────────────────────────────────────

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  activeIntent: string | null;
  pendingUpdates: MemoryUpdate[];

  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendToken: (id: string, token: string) => void;
  finalizeMessage: (id: string, updates: MemoryUpdate[]) => void;
  setIntent: (intent: string) => void;
  setStreaming: (v: boolean) => void;
  dismissUpdate: (index: number) => void;
  clearUpdates: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  activeIntent: null,
  pendingUpdates: [],

  addUserMessage: (content) => {
    const id = nanoid();
    set((s) => ({
      messages: [...s.messages, { id, role: "user", content }],
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = nanoid();
    set((s) => ({
      messages: [...s.messages, { id, role: "assistant", content: "", streaming: true }],
      isStreaming: true,
    }));
    return id;
  },

  appendToken: (id, token) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      ),
    }));
  },

  finalizeMessage: (id, updates) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, streaming: false, proposedUpdates: updates }
          : m
      ),
      isStreaming: false,
      pendingUpdates: updates,
    }));
  },

  setIntent: (intent) => set({ activeIntent: intent }),
  setStreaming: (v) => set({ isStreaming: v }),

  dismissUpdate: (index) =>
    set((s) => ({
      pendingUpdates: s.pendingUpdates.filter((_, i) => i !== index),
    })),

  clearUpdates: () => set({ pendingUpdates: [] }),
}));
