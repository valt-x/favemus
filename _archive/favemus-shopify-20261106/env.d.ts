/// <reference types="vite/client" />
/// <reference types="@react-router/node" />

import type { HTMLAttributes } from "react";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "s-app-nav": HTMLAttributes<HTMLElement>;
    }
  }
}
