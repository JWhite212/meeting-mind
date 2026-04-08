import { useQuery } from "@tanstack/react-query";
import { getStatus, getHealth } from "../lib/api";
import { STATUS_POLL_INTERVAL } from "../lib/constants";

export function useDaemonStatus() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: STATUS_POLL_INTERVAL,
    retry: false,
  });

  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
    refetchInterval: STATUS_POLL_INTERVAL,
    enabled: healthQuery.isSuccess,
    retry: false,
  });

  const daemonRunning = healthQuery.isSuccess;
  const state = statusQuery.data?.state ?? "unknown";
  const activeMeeting = statusQuery.data?.active_meeting ?? null;

  return {
    daemonRunning,
    state,
    activeMeeting,
    isLoading: healthQuery.isLoading,
  };
}
