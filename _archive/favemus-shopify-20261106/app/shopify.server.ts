import "@shopify/shopify-app-react-router/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-react-router/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";

export const APP_PRICING_ENABLED =
  process.env.APP_PRICING_ENABLED === "true";

const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_API_KEY,
  apiSecretKey: process.env.SHOPIFY_API_SECRET || "",
  apiVersion: ApiVersion.July26,
  scopes: process.env.SCOPES?.split(","),
  appUrl: process.env.SHOPIFY_APP_URL || "",
  authPathPrefix: "/auth",
  sessionStorage: new PrismaSessionStorage(prisma),
  distribution: AppDistribution.AppStore,
  future: {
    expiringOfflineAccessTokens: true,
  },
  ...(process.env.SHOP_CUSTOM_DOMAIN
    ? { customShopDomains: [process.env.SHOP_CUSTOM_DOMAIN] }
    : {}),
});

const DEFAULT_APP_HANDLE = "favemus-ai-support";

function storeHandle(shop: string) {
  return shop.replace(/\.myshopify\.com$/, "");
}

function partnerApiConfig() {
  const partnerId = process.env.PARTNER_API_ID?.trim();
  const accessToken = process.env.PARTNER_API_ACCESS_TOKEN?.trim();
  const apiVersion = process.env.PARTNER_API_VERSION?.trim() || "2026-10";

  if (!partnerId || !accessToken) return null;
  return { partnerId, accessToken, apiVersion };
}

export function pricingPlansUrl(shop: string, appHandle: string) {
  return `https://admin.shopify.com/store/${storeHandle(shop)}/charges/${appHandle}/pricing_plans`;
}

export async function getSubscriptionState(admin: {
  graphql: (query: string) => Promise<Response>;
}) {
  const response = await admin.graphql(
    `#graphql
    query AppInstallationIds {
      shop { id }
      currentAppInstallation {
        app { id handle }
      }
    }`,
  );
  const json = (await response.json()) as {
    data?: {
      shop?: { id?: string };
      currentAppInstallation?: {
        app?: { id?: string; handle?: string };
      };
    };
  };

  const appId = json.data?.currentAppInstallation?.app?.id || "";
  const shopId = json.data?.shop?.id || "";
  const appHandle =
    json.data?.currentAppInstallation?.app?.handle || DEFAULT_APP_HANDLE;

  if (!appId || !shopId) {
    throw new Error("Shopify app installation could not be resolved");
  }

  const config = partnerApiConfig();
  if (!config) {
    throw new Error(
      "Partner API credentials are required for Shopify App Pricing. Set PARTNER_API_ID and PARTNER_API_ACCESS_TOKEN.",
    );
  }

  const partnerResponse = await fetch(
    `https://partners.shopify.com/${config.partnerId}/api/${config.apiVersion}/graphql.json`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": config.accessToken,
      },
      body: JSON.stringify({
        query: `#graphql
          query ActiveSubscription($appId: ID!, $shopId: ID!) {
            activeSubscription(appId: $appId, shopId: $shopId) {
              billingPeriod
            }
          }`,
        variables: { appId, shopId },
      }),
    },
  );

  if (!partnerResponse.ok) {
    throw new Error(`Partner API request failed: ${partnerResponse.status}`);
  }

  const partnerJson = (await partnerResponse.json()) as {
    data?: { activeSubscription?: unknown };
    errors?: Array<{ message?: string }>;
  };

  if (partnerJson.errors?.length) {
    throw new Error(
      `Partner API request failed: ${partnerJson.errors[0]?.message || "unknown error"}`,
    );
  }

  return {
    appHandle,
    hasActiveSubscription: Boolean(partnerJson.data?.activeSubscription),
    subscriptionNames: [] as string[],
  };
}

export default shopify;
export const apiVersion = ApiVersion.July26;
export const addDocumentResponseHeaders = shopify.addDocumentResponseHeaders;
export const authenticate = shopify.authenticate;
export const unauthenticated = shopify.unauthenticated;
export const login = shopify.login;
export const registerWebhooks = shopify.registerWebhooks;
export const sessionStorage = shopify.sessionStorage;
