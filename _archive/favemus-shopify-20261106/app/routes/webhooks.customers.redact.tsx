import type { ActionFunctionArgs } from "react-router";
import { authenticate } from "../shopify.server";
import { purgeHarnessData } from "../harness.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, topic, payload } = await authenticate.webhook(request);
  const data = payload as { customer?: { id?: string | number } };
  const customerId =
    data.customer?.id != null ? String(data.customer.id) : undefined;

  console.log(
    `[compliance] ${topic} for ${shop} customer=${customerId ?? "unknown"}`,
  );

  if (customerId) {
    await purgeHarnessData(shop, customerId);
  }

  return new Response(null, { status: 200 });
};
