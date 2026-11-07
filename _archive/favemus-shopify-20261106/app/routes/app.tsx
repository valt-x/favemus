import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { Outlet, useLoaderData, useRouteError } from "react-router";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { AppProvider } from "@shopify/shopify-app-react-router/react";

import {
  APP_PRICING_ENABLED,
  authenticate,
  getSubscriptionState,
  pricingPlansUrl,
} from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { admin, redirect, session } = await authenticate.admin(request);
  const url = new URL(request.url);

  if (APP_PRICING_ENABLED && !url.pathname.startsWith("/app/billing")) {
    const state = await getSubscriptionState(admin);
    if (!state.hasActiveSubscription) {
      throw redirect(pricingPlansUrl(session.shop, state.appHandle), {
        target: "_top",
      });
    }
  }

  // eslint-disable-next-line no-undef
  return { apiKey: process.env.SHOPIFY_API_KEY || "" };
};

export default function App() {
  const { apiKey } = useLoaderData<typeof loader>();

  return (
    <AppProvider apiKey={apiKey}>
      <s-app-nav>
        <s-link href="/app">Dashboard</s-link>
        <s-link href="/app/sessions">Conversations</s-link>
        <s-link href="/app/tickets">Tickets</s-link>
        <s-link href="/app/billing">Plan</s-link>
      </s-app-nav>
      <Outlet />
    </AppProvider>
  );
}

// Shopify needs React Router to catch some thrown responses, so that their headers are included in the response.
export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
