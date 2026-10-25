import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

// Dismiss the boot splash (index.html) as soon as the app is ready. We keep a
// short anti-flicker floor so the splash never vanishes in a single frame on
// warm-cache loads, but we no longer force users to watch it for several
// seconds. (Slow loads only extend it further.)
const MIN_SPLASH_MS = 500;
const wait = Math.max(0, MIN_SPLASH_MS - performance.now());
setTimeout(() => document.documentElement.classList.add("js-ready"), wait);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
