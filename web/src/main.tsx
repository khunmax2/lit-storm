import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "next-themes";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiError } from "@/api/client";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider } from "@/i18n";
import { router } from "@/router";
import "@/styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx will not change by asking again.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <I18nProvider>
          <TooltipProvider>
            <RouterProvider router={router} />
            <Toaster richColors position="bottom-right" />
          </TooltipProvider>
        </I18nProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
