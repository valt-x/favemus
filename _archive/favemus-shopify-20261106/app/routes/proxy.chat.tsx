import type { ActionFunctionArgs, LoaderFunctionArgs } from "react-router";
import { authenticate } from "../shopify.server";

const HARNESS_URL = process.env.HARNESS_URL || "http://127.0.0.1:8091";

export async function loader({ request }: LoaderFunctionArgs) {
  await authenticate.public.appProxy(request);
  const url = new URL(request.url);
  return Response.json({ ok: true, shop: url.searchParams.get("shop") });
}

export async function action({ request }: ActionFunctionArgs) {
  await authenticate.public.appProxy(request);

  const url = new URL(request.url);
  const shop = url.searchParams.get("shop") || "unknown";
  const customerId = url.searchParams.get("logged_in_customer_id") || null;

  let body: { message?: string; session_id?: string } = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  const message = String(body.message || "").trim().slice(0, 2000);
  if (!message) {
    return Response.json({ error: "message required" }, { status: 400 });
  }

  const sessionId =
    String(body.session_id || "").trim().slice(0, 100) ||
    `web-${shop}-${Date.now()}`;

  const upstream = await fetch(`${HARNESS_URL}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_id: customerId,
      channel: "storefront",
      shop,
    }),
  });

  const data = await upstream
    .json()
    .catch(() => ({ error: "bad upstream response" }));

  return Response.json(data, { status: upstream.status });
}
