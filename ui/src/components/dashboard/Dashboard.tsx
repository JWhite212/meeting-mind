import { useQuery } from "@tanstack/react-query";
import { getMeetings } from "../../lib/api";
import { useDaemonStatus } from "../../hooks/useDaemonStatus";
import { useAppStore } from "../../stores/appStore";

function StatusCard() {
  const { daemonRunning, state, activeMeeting } = useDaemonStatus();
  const pipelineStage = useAppStore((s) => s.pipelineStage);

  if (!daemonRunning) {
    return (
      <div className="rounded-xl bg-surface-raised border border-border p-6">
        <div className="flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-status-error" />
          <div>
            <h3 className="text-sm font-medium text-text-primary">Daemon Offline</h3>
            <p className="text-xs text-text-muted mt-0.5">
              Start the daemon to begin detecting meetings
            </p>
          </div>
        </div>
      </div>
    );
  }

  const stateDisplay: Record<string, { label: string; color: string; description: string }> = {
    idle: {
      label: "Idle",
      color: "bg-status-idle",
      description: "Listening for Teams meetings...",
    },
    detecting: {
      label: "Detecting",
      color: "bg-amber-400",
      description: "Possible meeting detected, confirming...",
    },
    recording: {
      label: "Recording",
      color: "bg-status-recording animate-pulse",
      description: activeMeeting
        ? `Recording for ${Math.floor(activeMeeting.elapsed_seconds / 60)}m ${Math.floor(activeMeeting.elapsed_seconds % 60)}s`
        : "Meeting in progress",
    },
    processing: {
      label: pipelineStage ?? "Processing",
      color: "bg-blue-400",
      description: `Pipeline stage: ${pipelineStage ?? "..."}`,
    },
    unknown: {
      label: "Unknown",
      color: "bg-gray-400",
      description: "Waiting for status...",
    },
  };

  const currentState = state === "idle" && pipelineStage ? "processing" : state;
  const display = stateDisplay[currentState] ?? stateDisplay.unknown;

  return (
    <div className="rounded-xl bg-surface-raised border border-border p-6">
      <div className="flex items-center gap-3">
        <span className={`w-3 h-3 rounded-full ${display.color}`} />
        <div>
          <h3 className="text-sm font-medium text-text-primary">{display.label}</h3>
          <p className="text-xs text-text-muted mt-0.5">{display.description}</p>
        </div>
      </div>
    </div>
  );
}

function RecentMeetings() {
  const { daemonRunning } = useDaemonStatus();

  const { data, isLoading } = useQuery({
    queryKey: ["meetings", "recent"],
    queryFn: () => getMeetings(10, 0),
    enabled: daemonRunning,
    refetchInterval: 10000,
  });

  if (!daemonRunning) return null;

  if (isLoading) {
    return (
      <div className="rounded-xl bg-surface-raised border border-border p-6">
        <h2 className="text-sm font-medium text-text-primary mb-4">Recent Meetings</h2>
        <p className="text-xs text-text-muted">Loading...</p>
      </div>
    );
  }

  const meetings = data?.meetings ?? [];

  return (
    <div className="rounded-xl bg-surface-raised border border-border p-6">
      <h2 className="text-sm font-medium text-text-primary mb-4">Recent Meetings</h2>
      {meetings.length === 0 ? (
        <p className="text-xs text-text-muted">
          No meetings yet. Meetings will appear here once the daemon records and processes them.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {meetings.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-sidebar-hover transition-colors cursor-pointer"
            >
              <div className="min-w-0">
                <p className="text-sm text-text-primary truncate">{m.title}</p>
                <p className="text-xs text-text-muted">
                  {new Date(m.started_at * 1000).toLocaleDateString()}
                  {m.duration_seconds && ` \u00B7 ${Math.round(m.duration_seconds / 60)}m`}
                </p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  m.status === "complete"
                    ? "bg-status-idle/20 text-status-idle"
                    : m.status === "error"
                      ? "bg-status-error/20 text-status-error"
                      : "bg-blue-400/20 text-blue-400"
                }`}
              >
                {m.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Dashboard() {
  return (
    <div className="flex flex-col gap-4 p-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-text-primary">Dashboard</h1>
      <StatusCard />
      <RecentMeetings />
    </div>
  );
}
