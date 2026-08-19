import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

// Dismiss the boot splash (index.html) when the app is ready, but hold it
// on screen for a minimum of 3 seconds from navigation start so the splash
// is visible even on fast local loads. (Slow loads only extend it further.)
const MIN_SPLASH_MS = 3000;
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
