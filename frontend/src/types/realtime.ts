export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export interface RealtimeMessage {
  type: string;
  event_id: string;
  occurred_at: string;
  correlation_id?: string | null;
  data: {
    title?: string;
    message?: string;
    severity?: "info" | "warning" | "high";
    amount?: string;
    role?: "sender" | "receiver";
    risk_level?: string;
    [key: string]: unknown;
  };
}

export interface RealtimeNotification {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "high";
  occurredAt: string;
  type: string;
}
