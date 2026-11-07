import type { ActionFunctionArgs, LoaderFunctionArgs } from "react-router";
import { Form, redirect, useLoaderData } from "react-router";
import { authenticate } from "../shopify.server";
import {
  closeHarnessTicket,
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
  const tickets = await getHarnessTickets(session.shop);
  return {
    tickets: tickets.map((ticket) => ({
      ...ticket,
      order_id: orderFromPayload(ticket.payload),
    })),
  };
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const ticketId = Number(form.get("ticket_id"));

  if (!Number.isInteger(ticketId)) {
    throw new Response("Bad request", { status: 400 });
  }

  const tickets = await getHarnessTickets(session.shop);
  if (!tickets.some((ticket) => ticket.id === ticketId)) {
    throw new Response("Not found", { status: 404 });
  }

  await closeHarnessTicket(ticketId);
  return redirect("/app/tickets");
};

export default function TicketsPage() {
  const { tickets } = useLoaderData<typeof loader>();

  return (
    <s-page heading="Tickets">
      <s-section heading="Support tickets">
        {tickets.length ? (
          <s-unordered-list>
            {tickets.map((ticket) => (
              <s-list-item key={ticket.id}>
                #{ticket.id} · {ticket.kind} · {ticket.status} ·{" "}
                {ticket.order_id || ticket.session_id || "conversation"} ·{" "}
                {when(ticket.created_at)}
                {ticket.status === "open" ? (
                  <Form method="post">
                    <input
                      type="hidden"
                      name="ticket_id"
                      value={String(ticket.id)}
                    />
                    <s-button type="submit" variant="secondary">
                      Close ticket
                    </s-button>
                  </Form>
                ) : null}
              </s-list-item>
            ))}
          </s-unordered-list>
        ) : (
          <s-paragraph>No tickets yet.</s-paragraph>
        )}
      </s-section>
    </s-page>
  );
}
