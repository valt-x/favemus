import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";
import { authenticate } from "../shopify.server";
import {
  getHarnessMetrics,
  getHarnessSessions,
  getHarnessTickets,
} from "../harness.server";

function when(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

function orderFromPayload(payload?: string | null) {
  if (!payload) return "";
  try {
    const data = JSON.parse(payload);
    return data.order_id || data.size || "";
  } catch {
    return "";
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const [metrics, sessions, tickets] = await Promise.all([
    getHarnessMetrics(shop),
    getHarnessSessions(shop),
    getHarnessTickets(shop),
  ]);

  return {
    shop,
    metrics,
    sessions: sessions.slice(0, 8),
    openTickets: tickets
      .filter((ticket) => ticket.status === "open")
      .slice(0, 8)
      .map((ticket) => ({
        ...ticket,
        order_id: orderFromPayload(ticket.payload),
      })),
  };
};

export default function Index() {
  const { shop, metrics, sessions, openTickets } =
    useLoaderData<typeof loader>();

  return (
    <s-page heading="Support dashboard">
      <s-section heading="Overview">
        <s-paragraph>Store: {shop}</s-paragraph>
        <s-paragraph>
          {metrics.decisions} AI decisions · {metrics.open_tickets} open
          tickets · {Math.round(metrics.handoff_rate * 100)}% handoffs ·{" "}
          {Math.round(metrics.avg_latency_ms)} ms average
        </s-paragraph>
      </s-section>

      <s-section heading="Recent conversations">
        {sessions.length ? (
          <s-unordered-list>
            {sessions.map((conversation) => (
              <s-list-item key={conversation.id}>
                <s-link href={`/app/sessions/${encodeURIComponent(conversation.id)}`}>
                  {conversation.id}
                </s-link>{" "}
                · {conversation.channel || "web"} ·{" "}
                {conversation.user_id || "anonymous"} ·{" "}
                {conversation.state || "idle"} ·{" "}
                {when(conversation.updated_at)}
              </s-list-item>
            ))}
          </s-unordered-list>
        ) : (
          <s-paragraph>No conversations yet.</s-paragraph>
        )}
        <s-paragraph>
          <s-link href="/app/sessions">View all conversations</s-link>
        </s-paragraph>
      </s-section>

      <s-section heading="Open tickets">
        {openTickets.length ? (
          <s-unordered-list>
            {openTickets.map((ticket) => (
              <s-list-item key={ticket.id}>
                #{ticket.id} · {ticket.kind} ·{" "}
                {ticket.order_id || ticket.session_id || "conversation"} ·{" "}
                {when(ticket.created_at)}
              </s-list-item>
            ))}
          </s-unordered-list>
        ) : (
          <s-paragraph>No open tickets.</s-paragraph>
        )}
        <s-paragraph>
          <s-link href="/app/tickets">Manage tickets</s-link>
        </s-paragraph>
      </s-section>
    </s-page>
  );
}
