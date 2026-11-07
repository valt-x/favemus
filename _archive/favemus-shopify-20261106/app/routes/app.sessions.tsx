import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";
import { authenticate } from "../shopify.server";
import { getHarnessSessions } from "../harness.server";

function when(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const conversations = await getHarnessSessions(session.shop);
  return { conversations };
};

export default function SessionsPage() {
  const { conversations } = useLoaderData<typeof loader>();

  return (
    <s-page heading="Conversations">
      <s-section heading="Recent conversations">
        {conversations.length ? (
          <s-unordered-list>
            {conversations.map((conversation) => (
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
      </s-section>
    </s-page>
  );
}
