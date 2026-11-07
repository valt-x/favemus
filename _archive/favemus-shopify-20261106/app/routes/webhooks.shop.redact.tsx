import type { ActionFunctionArgs } from "react-router";
import { authenticate } from "../shopify.server";
import db from "../db.server";
import { purgeHarnessData } from "../harness.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, topic } = await authenticate.webhook(request);

  console.log(`[compliance] ${topic} for ${shop}`);

  await purgeHarnessData(shop);
  await db.session.deleteMany({ where: { shop } });

  return new Response(null, { status: 200 });
};
