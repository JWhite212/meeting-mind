import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAppStore } from "../../stores/appStore";
import { usePipelineSync } from "../usePipelineSync";

// usePipelineSync depends on useDaemonStatus to know whether the daemon is
// actually doing pipeline work. The mock is hoisted before the hook is loaded.
const mockUseDaemonStatus = vi.fn();
vi.mock("../useDaemonStatus", () => ({
  useDaemonStatus: () => mockUseDaemonStatus(),
}));

describe("usePipelineSync (Bug C1 fix)", () => {
  beforeEach(() => {
    // Reset zustand store to a clean state between tests.
    useAppStore.setState({
      pipelineStage: null,
      liveSegments: [],
      audioLevels: { system: 0, mic: 0 },
    });
    mockUseDaemonStatus.mockReset();
  });

  afterEach(() => {
    useAppStore.setState({
      pipelineStage: null,
      liveSegments: [],
      audioLevels: { system: 0, mic: 0 },
    });
  });

  it("clears stale pipelineStage when daemon reports idle and no active meeting", async () => {
    // Reproduce the user-visible bug: WebSocket dropped while the daemon
    // was 'summarising', so the terminal pipeline.complete event was lost.
    // The store still says 'summarising' and the UI shows "Processing..."
    // forever. The new sync hook should reconcile by polling the daemon's
    // authoritative state and clearing stale pipelineStage when the daemon
    // says it isn't doing anything.
    useAppStore.setState({ pipelineStage: "summarising" });
    mockUseDaemonStatus.mockReturnValue({
      daemonRunning: true,
      state: "idle",
      activeMeeting: null,
      isLoading: false,
    });

    renderHook(() => usePipelineSync());

    await waitFor(() => {
      expect(useAppStore.getState().pipelineStage).toBeNull();
    });
  });

  it("does not clear pipelineStage while the daemon is still recording", async () => {
    // If the daemon is actively recording or has an active meeting, the
    // pipelineStage is legitimate — don't reset it.
    useAppStore.setState({ pipelineStage: "transcribing" });
    mockUseDaemonStatus.mockReturnValue({
      daemonRunning: true,
      state: "recording",
      activeMeeting: { meeting_id: "abc", started_at: 0, elapsed_seconds: 0 },
      isLoading: false,
    });

    renderHook(() => usePipelineSync());

    // Give any async effects a tick to run.
    await new Promise((r) => setTimeout(r, 50));
    expect(useAppStore.getState().pipelineStage).toBe("transcribing");
  });

  it("does not clear pipelineStage when the daemon is unreachable", async () => {
    // If daemonRunning is false we don't have authoritative state — leave
    // the store alone rather than racing the reconnect.
    useAppStore.setState({ pipelineStage: "summarising" });
    mockUseDaemonStatus.mockReturnValue({
      daemonRunning: false,
      state: "unknown",
      activeMeeting: null,
      isLoading: false,
    });

    renderHook(() => usePipelineSync());

    await new Promise((r) => setTimeout(r, 50));
    expect(useAppStore.getState().pipelineStage).toBe("summarising");
  });
});
