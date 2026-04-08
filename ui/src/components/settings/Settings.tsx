import { useDaemonStatus } from "../../hooks/useDaemonStatus";
import { useAppStore } from "../../stores/appStore";

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between py-2">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-sm text-text-primary font-mono">{value}</span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-surface-raised border border-border p-5">
      <h2 className="text-sm font-medium text-text-primary mb-3">{title}</h2>
      <div className="divide-y divide-border">{children}</div>
    </div>
  );
}

export function Settings() {
  const { daemonRunning, state } = useDaemonStatus();
  const wsConnected = useAppStore((s) => s.wsConnected);

  return (
    <div className="flex flex-col gap-4 p-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-text-primary">Settings</h1>

      <Section title="Daemon">
        <InfoRow label="Status" value={daemonRunning ? "Running" : "Offline"} />
        <InfoRow label="State" value={state} />
        <InfoRow label="WebSocket" value={wsConnected ? "Connected" : "Disconnected"} />
        <InfoRow label="API" value="http://127.0.0.1:9876" />
      </Section>

      <Section title="Storage">
        <InfoRow label="Database" value="~/.local/share/meetingmind/meetings.db" />
        <InfoRow label="Audio" value="~/.local/share/meetingmind/audio/" />
        <InfoRow label="Auth token" value="~/.config/meetingmind/auth_token" />
        <InfoRow label="Logs" value="~/Library/Logs/meetingmind.log" />
      </Section>

      <Section title="Configuration">
        <div className="py-3">
          <p className="text-sm text-text-secondary">
            Edit <code className="text-xs px-1.5 py-0.5 rounded bg-surface border border-border font-mono">config.yaml</code> in the project root to change settings.
          </p>
          <p className="text-xs text-text-muted mt-2">
            Restart the daemon after making changes.
          </p>
        </div>
      </Section>

      <Section title="About">
        <InfoRow label="App" value="MeetingMind" />
        <InfoRow label="Version" value="0.1.0" />
        <InfoRow label="Platform" value="macOS (Tauri)" />
      </Section>
    </div>
  );
}
