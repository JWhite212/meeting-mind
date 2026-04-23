import { create } from "zustand";
import type { WSEvent, TranscriptSegment } from "../lib/types";

let lastLevelUpdate = 0;

interface AudioLevels {
  system: number;
  mic: number;
}

interface ModelProgress {
  percent: number;
  error?: string;
}

interface AppState {
  /** WebSocket connection status. */
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  /** Current pipeline stage for the active meeting. */
  pipelineStage: string | null;

  /** Live transcript segments for the active meeting. */
  liveSegments: TranscriptSegment[];

  /** Live audio levels (RMS, 0.0–1.0). */
  audioLevels: AudioLevels;

  /** Model download progress from WebSocket events. */
  modelProgress: Record<string, ModelProgress>;

  /** Whether the microphone was unavailable at recording start. */
  micUnavailable: boolean;

  /** Unread notification count. */
  unreadNotifications: number;
  incrementNotifications: () => void;
  setUnreadNotifications: (count: number) => void;

  /** Handle a WebSocket event. */
  handleEvent: (event: WSEvent) => void;

  /** Reset live state (e.g., when a meeting completes). */
  resetLive: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  pipelineStage: null,
  liveSegments: [],
  audioLevels: { system: 0, mic: 0 },
  modelProgress: {},

  micUnavailable: false,
  unreadNotifications: 0,
  incrementNotifications: () =>
    set((state) => ({ unreadNotifications: state.unreadNotifications + 1 })),
  setUnreadNotifications: (count) => set({ unreadNotifications: count }),

  handleEvent: (event) => {
    switch (event.type) {
      case "pipeline.stage":
        set({ pipelineStage: event.stage });
        break;
      case "pipeline.complete":
        set({
          pipelineStage: null,
          liveSegments: [],
          audioLevels: { system: 0, mic: 0 },
        });
        break;
      case "pipeline.error":
        set({ pipelineStage: null, audioLevels: { system: 0, mic: 0 } });
        break;
      case "transcript.segment":
        if (!event.segment?.text?.trim()) break;
        set((state) => {
          const segments = [...state.liveSegments, event.segment];
          return {
            liveSegments:
              segments.length > 200 ? segments.slice(-200) : segments,
          };
        });
        break;
      case "audio.level": {
        const now = Date.now();
        if (now - lastLevelUpdate < 250) break;
        lastLevelUpdate = now;
        set({
          audioLevels: {
            system: event.system_rms ?? 0,
            mic: event.mic_rms ?? 0,
          },
        });
        break;
      }
      case "model.download.progress":
        set((state) => ({
          modelProgress: {
            ...state.modelProgress,
            [event.model]: { percent: event.percent, error: event.error },
          },
        }));
        break;
      case "audio.mic_unavailable":
        set({ micUnavailable: true });
        break;
      case "meeting.started":
        set({ micUnavailable: false });
        break;
      case "notification":
        set((state) => ({
          unreadNotifications: state.unreadNotifications + 1,
        }));
        break;
    }
  },

  resetLive: () =>
    set({
      pipelineStage: null,
      liveSegments: [],
      audioLevels: { system: 0, mic: 0 },
    }),
}));
