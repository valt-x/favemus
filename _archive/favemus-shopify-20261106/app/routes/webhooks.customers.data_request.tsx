import type { ActionFunctionArgs } from "react-router";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, topic, payload } = await authenticate.webhook(request);
  const data = payload as {
    customer?: { id?: string | number };
    orders_requested?: unknown[];
  };
  const orders = Array.isArray(data.orders_requested)
    ? data.orders_requested.length
    : 0;

  console.log(
    `[compliance] ${topic} for ${shop} customer=${data.customer?.id ?? "unknown"} orders=${orders}`,
  );

  return new Response(null, { status: 200 });
};
