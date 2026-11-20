import type { MonitorStatus } from "../types";

export const STATUS_META: Record<MonitorStatus, { icon: string; text: string; tone: string }> = {
  HEALTHY: { icon: "🌸", text: "Healthy", tone: "ok" },
  EXPIRING_SOON: { icon: "🍑", text: "Expiring soon", tone: "warn" },
  EXPIRED: { icon: "🥀", text: "Expired", tone: "bad" },
  INVALID: { icon: "⚠️", text: "Invalid", tone: "bad" },
  CHECK_FAILED: { icon: "🔌", text: "Check failed", tone: "muted" },
  CHANGED: { icon: "🔄", text: "Changed", tone: "info" },
};

export function MonitorStatusBadge({ status }: { status: MonitorStatus }) {
  const m = STATUS_META[status];
  return (
    <span className={`mstatus mstatus-${m.tone}`} data-testid={`status-${status}`}>
      <span aria-hidden="true">{m.icon}</span> {m.text}
    </span>
  );
}
