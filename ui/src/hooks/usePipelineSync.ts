import { useEffect } from "react";
import { useAppStore } from "../stores/appStore";
import { useDaemonStatus } from "./useDaemonStatus";

/**
 * Reconcile in-memory pipelineStage with the daemon's authoritative state.
 *
 * If the WebSocket dropped during a pipeline run, the terminal
 * pipeline.complete / pipeline.error event may have been lost — leaving
 * pipelineStage stuck on a non-null value and the UI showing
 * "Processing..." indefinitely (Bug C1). useDaemonStatus already polls
 * /api/status, so we use its result as the source of truth: if the daemon
 * is idle with no active meeting, any in-memory pipelineStage is stale.
 */
export function usePipelineSync(): void {
  const { daemonRunning, state, activeMeeting } = useDaemonStatus();
  const pipelineStage = useAppStore((s) => s.pipelineStage);
  const resetLive = useAppStore((s) => s.resetLive);

  useEffect(() => {
    if (!daemonRunning) return;
    if (pipelineStage === null) return;
    if (state === "idle" && activeMeeting === null) {
      resetLive();
    }
  }, [daemonRunning, state, activeMeeting, pipelineStage, resetLive]);
}
