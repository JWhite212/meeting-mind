import { useEffect, useRef } from "react";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";
import type { WSEvent } from "../lib/types";

/**
 * Listens for WebSocket events and fires macOS notifications
 * for key meeting lifecycle moments.
 */
export function useNotifications(lastEvent: WSEvent | null) {
  const permissionRef = useRef(false);

  // Request notification permission on mount.
  useEffect(() => {
    (async () => {
      let granted = await isPermissionGranted();
      if (!granted) {
        const result = await requestPermission();
        granted = result === "granted";
      }
      permissionRef.current = granted;
    })();
  }, []);

  // React to events.
  useEffect(() => {
    if (!lastEvent || !permissionRef.current) return;

    switch (lastEvent.type) {
      case "meeting.started":
        sendNotification({
          title: "Meeting Detected",
          body: "Recording has started automatically.",
        });
        break;

      case "meeting.ended":
        sendNotification({
          title: "Meeting Ended",
          body: "Processing recording...",
        });
        break;

      case "pipeline.complete":
        sendNotification({
          title: "Meeting Processed",
          body: lastEvent.title
            ? `"${lastEvent.title}" is ready to review.`
            : "Summary and transcript are ready.",
        });
        break;

      case "pipeline.error":
        sendNotification({
          title: "Processing Error",
          body: lastEvent.error
            ? `Failed: ${lastEvent.error}`
            : "An error occurred during processing.",
        });
        break;
    }
  }, [lastEvent]);
}
