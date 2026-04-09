import { create } from "zustand";
import type { WSEvent, TranscriptSegment } from "../lib/types";

interface AudioLevels {
  system: number;
  mic: number;
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

  handleEvent: (event) => {
    switch (event.type) {
      case "pipeline.stage":
        set({ pipelineStage: event.stage });
        break;
      case "pipeline.complete":
        set({ pipelineStage: null, liveSegments: [], audioLevels: { system: 0, mic: 0 } });
        break;
      case "pipeline.error":
        set({ pipelineStage: null, audioLevels: { system: 0, mic: 0 } });
        break;
      case "transcript.segment":
        set((state) => ({
          liveSegments: [...state.liveSegments, event.segment],
        }));
        break;
      case "audio.level":
        set({ audioLevels: { system: event.system_rms ?? 0, mic: event.mic_rms ?? 0 } });
        break;
    }
  },

  resetLive: () => set({ pipelineStage: null, liveSegments: [], audioLevels: { system: 0, mic: 0 } }),
}));
