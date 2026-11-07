export default function Privacy() {
  return (
    <main
      style={{
        fontFamily:
          "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        maxWidth: 760,
        margin: "0 auto",
        padding: "48px 24px",
        lineHeight: 1.6,
        color: "#1a1a1a",
      }}
    >
      <h1>Privacy Policy</h1>
      <p>Last updated: 4 November 2026</p>
      <p>
        Favemus AI Support (&quot;Favemus&quot;, &quot;we&quot;, &quot;us&quot;) provides AI-assisted customer
        support for Shopify merchants. This policy explains what data we process
        and why.
      </p>

      <h2>Data we process</h2>
      <ul>
        <li>
          Store and account data: your Shopify store domain and the access token
          needed to provide the service.
        </li>
        <li>
          Customer conversation data: messages sent through the Shopify
          storefront chat widget, plus the order number or product details you
          include in those messages.
        </li>
        <li>
          Order data: order status, line items, totals, fulfilment, refund, and
          return status, read from Shopify when a customer asks about an order.
        </li>
        <li>
          Support records: tickets created for returns, exchanges, and human
          handoffs.
        </li>
      </ul>

      <h2>Why we process it</h2>
      <p>
        We use this data only to answer customer support questions, create
        return or exchange requests, and pass conversations to a human agent
        when needed. We do not sell personal data or use it for advertising.
      </p>

      <h2>Storage and retention</h2>
      <p>
        Chat sessions and support tickets are stored in our database for as long
        as needed to provide the service, normally no longer than 90 days unless
        the merchant asks us to keep them longer. Shopify order data is read on
        demand and is not stored beyond the support ticket that references it.
      </p>

      <h2>Sharing</h2>
      <p>
        We share data only with service providers that host the application and
        with Shopify as needed to provide the app. We do not share customer data
        with third parties for marketing.
      </p>

      <h2>Your rights</h2>
      <p>
        Merchants and customers may request access, correction, or deletion of
        their data by contacting{" "}
        <a href="mailto:xpanda@tutanota.de">xpanda@tutanota.de</a>. We respond
        within 30 days.
      </p>

      <h2>Cookies and local storage</h2>
      <p>
        The storefront chat stores a random session identifier in the browser&apos;s
        local storage so the conversation continues after a page reload. The
        app does not use advertising cookies.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy:{" "}
        <a href="mailto:xpanda@tutanota.de">xpanda@tutanota.de</a>.
      </p>
    </main>
  );
}
