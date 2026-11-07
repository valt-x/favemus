import { loadEnvFile } from "node:process";

try {
  loadEnvFile();
} catch {
  // No .env file in production; environment is provided by the platform.
}

const HARNESS_URL = (process.env.HARNESS_URL || "http://127.0.0.1:8091").replace(
  /\/$/,
  "",
);
const HARNESS_ADMIN_TOKEN = process.env.HARNESS_ADMIN_TOKEN || "";

export async function purgeHarnessData(shop: string, customerId?: string) {
  if (!HARNESS_ADMIN_TOKEN) {
    console.warn("HARNESS_ADMIN_TOKEN is not set; skipping harness purge");
    return { skipped: true };
  }

  const response = await fetch(`${HARNESS_URL}/harness/purge`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Harness-Token": HARNESS_ADMIN_TOKEN,
    },
    body: JSON.stringify({
      shop,
      customer_id: customerId ?? null,
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `harness purge failed (${response.status}): ${detail.slice(0, 200)}`,
    );
  }

  return response.json();
}

export type HarnessSession = {
  id: string;
  user_id?: string | null;
  channel?: string | null;
  shop?: string | null;
  state?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type HarnessTicket = {
  id: number;
  session_id?: string | null;
  shop?: string | null;
  kind?: string | null;
  status?: string | null;
  payload?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type HarnessMessage = {
  role?: string | null;
  content?: string | null;
  meta?: string | null;
  created_at?: string | null;
};

export type HarnessDecision = {
  message?: string | null;
  analysis?: string | null;
  tool_call?: string | null;
  action?: string | null;
  latency_ms?: number | null;
  created_at?: string | null;
};

export type HarnessMetrics = {
  decisions: number;
  handoff_rate: number;
  avg_latency_ms: number;
  open_tickets: number;
  by_action: Record<string, number>;
};

async function harnessFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${HARNESS_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(HARNESS_ADMIN_TOKEN
        ? { "X-Harness-Token": HARNESS_ADMIN_TOKEN }
        : {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `harness request failed (${response.status}): ${detail.slice(0, 200)}`,
    );
  }

  return response.json() as Promise<T>;
}

export async function getHarnessSessions(shop: string) {
  const data = await harnessFetch<{ sessions: HarnessSession[] }>(
    `/harness/sessions?shop=${encodeURIComponent(shop)}`,
  );
  return data.sessions || [];
}

export async function getHarnessSession(sessionId: string) {
  return harnessFetch<{
    session: HarnessSession;
    messages: HarnessMessage[];
    decisions: HarnessDecision[];
  }>(`/harness/sessions/${encodeURIComponent(sessionId)}`);
}

export async function getHarnessTickets(shop: string) {
  const data = await harnessFetch<{ tickets: HarnessTicket[] }>(
    `/harness/tickets?shop=${encodeURIComponent(shop)}`,
  );
  return data.tickets || [];
}

export async function getHarnessMetrics(shop: string) {
  return harnessFetch<HarnessMetrics>(
    `/harness/metrics?shop=${encodeURIComponent(shop)}`,
  );
}

export async function closeHarnessTicket(ticketId: number) {
  return harnessFetch<{ ticket_id: number; status: string }>(
    `/harness/tickets/${ticketId}/close`,
    { method: "POST" },
  );
}
