import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";
import {
  APP_PRICING_ENABLED,
  authenticate,
  getSubscriptionState,
  pricingPlansUrl,
} from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { admin, redirect, session } = await authenticate.admin(request);

  if (!APP_PRICING_ENABLED) {
    return {
      enabled: false,
      hasActiveSubscription: false,
      subscriptionNames: [] as string[],
      planUrl: "",
    };
  }

  const state = await getSubscriptionState(admin);
  const planUrl = pricingPlansUrl(session.shop, state.appHandle);

  if (!state.hasActiveSubscription) {
    throw redirect(planUrl, { target: "_top" });
  }

  return {
    enabled: true,
    hasActiveSubscription: true,
    subscriptionNames: state.subscriptionNames,
    planUrl,
  };
};

export default function BillingPage() {
  const { enabled, hasActiveSubscription, subscriptionNames } =
    useLoaderData<typeof loader>();

  return (
    <s-page heading="Plan">
      <s-section heading="Favemus AI Support">
        {!enabled ? (
          <s-paragraph>
            App pricing is not enabled yet. Set APP_PRICING_ENABLED=true after
            configuring the plan in Shopify App Pricing.
          </s-paragraph>
        ) : hasActiveSubscription ? (
          <>
            <s-paragraph>
              Active plan: {subscriptionNames.join(", ") || "Shopify App Pricing"}
            </s-paragraph>
            <s-paragraph>
              You can change or cancel your subscription from Shopify admin
              under Settings, Apps and sales channels.
            </s-paragraph>
          </>
        ) : null}
      </s-section>
    </s-page>
  );
}
