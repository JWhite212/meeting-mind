import { create } from "zustand";
import type { WSEvent, TranscriptSegment } from "../lib/types";

interface AppState {
  /** WebSocket connection status. */
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  /** Current pipeline stage for the active meeting. */
  pipelineStage: string | null;

  /** Live transcript segments for the active meeting. */
  liveSegments: TranscriptSegment[];

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

  handleEvent: (event) => {
    switch (event.type) {
      case "pipeline.stage":
        set({ pipelineStage: event.stage });
        break;
      case "pipeline.complete":
        set({ pipelineStage: null, liveSegments: [] });
        break;
      case "pipeline.error":
        set({ pipelineStage: null });
        break;
      case "transcript.segment":
        set((state) => ({
          liveSegments: [...state.liveSegments, event.segment],
        }));
        break;
    }
  },

  resetLive: () => set({ pipelineStage: null, liveSegments: [] }),
}));
