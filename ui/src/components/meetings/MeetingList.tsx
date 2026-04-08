import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getMeetings } from "../../lib/api";
import { useDaemonStatus } from "../../hooks/useDaemonStatus";
import type { MeetingStatus } from "../../lib/types";

const STATUS_FILTERS: { label: string; value: MeetingStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Complete", value: "complete" },
  { label: "Recording", value: "recording" },
  { label: "Error", value: "error" },
];

const PAGE_SIZE = 20;

export function MeetingList() {
  const navigate = useNavigate();
  const { daemonRunning } = useDaemonStatus();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<MeetingStatus | "all">("all");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["meetings", statusFilter, page, search],
    queryFn: () =>
      getMeetings(
        PAGE_SIZE,
        page * PAGE_SIZE,
        search || undefined,
      ),
    enabled: daemonRunning,
    refetchInterval: 10000,
  });

  const meetings = data?.meetings ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4 p-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-text-primary">Meetings</h1>

      {!daemonRunning ? (
        <p className="text-sm text-text-muted">
          Start the daemon to view meeting history.
        </p>
      ) : (
        <>
          {/* Search + filters */}
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Search meetings..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-surface-raised border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          <div className="flex gap-1.5">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setStatusFilter(f.value);
                  setPage(0);
                }}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  statusFilter === f.value
                    ? "bg-accent text-white"
                    : "bg-surface-raised text-text-secondary hover:bg-sidebar-hover"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Meeting list */}
          {isLoading ? (
            <p className="text-xs text-text-muted">Loading...</p>
          ) : meetings.length === 0 ? (
            <div className="rounded-xl bg-surface-raised border border-border p-6">
              <p className="text-sm text-text-muted">
                {search
                  ? "No meetings match your search."
                  : "No meetings yet. Meetings will appear here once the daemon records them."}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {meetings.map((m) => (
                <button
                  key={m.id}
                  onClick={() => navigate(`/meetings/${m.id}`)}
                  className="flex items-center justify-between py-3 px-4 rounded-xl bg-surface-raised border border-border hover:border-accent/40 transition-colors text-left"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {m.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-text-muted">
                        {new Date(m.started_at * 1000).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                      {m.duration_seconds != null && (
                        <span className="text-xs text-text-muted">
                          {Math.round(m.duration_seconds / 60)}m
                        </span>
                      )}
                      {m.word_count != null && (
                        <span className="text-xs text-text-muted">
                          {m.word_count.toLocaleString()} words
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    {m.tags.length > 0 && (
                      <div className="flex gap-1">
                        {m.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
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
                </button>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-text-muted">
                {total} meeting{total !== 1 ? "s" : ""}
              </span>
              <div className="flex gap-1">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1 text-xs rounded-lg bg-surface-raised border border-border text-text-secondary hover:bg-sidebar-hover disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Prev
                </button>
                <span className="px-2 py-1 text-xs text-text-muted">
                  {page + 1} / {totalPages}
                </span>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1 text-xs rounded-lg bg-surface-raised border border-border text-text-secondary hover:bg-sidebar-hover disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
