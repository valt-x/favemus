import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";
import { authenticate } from "../shopify.server";
import { getHarnessSession } from "../harness.server";

function when(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const sessionId = params.sid;
  if (!sessionId) {
    throw new Response("Not found", { status: 404 });
  }

  const data = await getHarnessSession(sessionId);
  if (data.session.shop !== session.shop) {
    throw new Response("Not found", { status: 404 });
  }

  return data;
};

export default function SessionDetailPage() {
  const { session, messages, decisions } = useLoaderData<typeof loader>();
  const updated = when(session.updated_at);

  return (
    <s-page heading={`Conversation ${session.id}`}>
      <s-section
        heading={`${session.channel || "web"} · ${session.user_id || "anonymous"} · ${session.state || "idle"}`}
      >
        <s-paragraph>
          <s-link href="/app/sessions">Back to conversations</s-link>
          {updated ? ` · Updated ${updated}` : ""}
        </s-paragraph>
        {messages.length ? (
          messages.map((message, index) => (
            <s-paragraph key={index}>
              <strong>{message.role || "message"}:</strong>{" "}
              {message.content || ""}
            </s-paragraph>
          ))
        ) : (
          <s-paragraph>No messages in this conversation.</s-paragraph>
        )}
      </s-section>

      <s-section heading="Decisions">
        {decisions.length ? (
          <s-unordered-list>
            {decisions.map((decision, index) => (
              <s-list-item key={index}>
                {decision.action || "unknown"} ·{" "}
                {Math.round(decision.latency_ms || 0)} ms ·{" "}
                {when(decision.created_at)}
              </s-list-item>
            ))}
          </s-unordered-list>
        ) : (
          <s-paragraph>No decisions recorded.</s-paragraph>
        )}
      </s-section>
    </s-page>
  );
}
