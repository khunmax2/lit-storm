import { useQuery } from "@tanstack/react-query";
import { Outlet, createRootRoute, createRoute, createRouter, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";

import { ApiError, api, call } from "@/api/client";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { useT, type Lang } from "@/i18n";
import { AdminPage } from "@/pages/admin";
import { LoginPage, SetPasswordPage, SetupPage } from "@/pages/auth";
import { HomePage } from "@/pages/home";
import { ReportPage } from "@/pages/report";
import { ProjectPage, ProjectsPage, SessionPage } from "@/pages/research";
import { TrashPage } from "@/pages/trash";

// Everything behind sign-in. Not signed in: the first-run setup page if the
// system has no Administrator yet, otherwise the sign-in page.
function SignedIn() {
  const { lang, setLang } = useT();
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["me"], queryFn: () => call(api.GET("/api/me")), retry: false });
  const unauthorised = me.error instanceof ApiError && me.error.status === 401;

  useEffect(() => {
    if (!unauthorised) return;
    call(api.GET("/api/setup")).then((s) => navigate({ to: s.needed ? "/setup" : "/login" }));
  }, [unauthorised, navigate]);

  useEffect(() => {
    // The account remembers its screen language across devices.
    if (me.data && me.data.ui_language !== lang) setLang(me.data.ui_language as Lang);
  }, [me.data?.ui_language]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!me.data)
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  return (
    <SidebarProvider>
      <AppSidebar me={me.data} />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
          <div id="page-toolbar" className="flex min-w-0 flex-1 items-center gap-2" />
        </header>
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  );
}

const rootRoute = createRootRoute({ component: Outlet });

const setupRoute = createRoute({ getParentRoute: () => rootRoute, path: "setup", component: SetupPage });
const loginRoute = createRoute({ getParentRoute: () => rootRoute, path: "login", component: LoginPage });
const setPasswordRoute = createRoute({ getParentRoute: () => rootRoute, path: "set-password", component: SetPasswordPage });

const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: SignedIn });
const homeRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: HomePage });
const projectsRoute = createRoute({ getParentRoute: () => appRoute, path: "projects", component: ProjectsPage });
const projectRoute = createRoute({ getParentRoute: () => appRoute, path: "projects/$projectId", component: ProjectPage });
const sessionRoute = createRoute({ getParentRoute: () => appRoute, path: "sessions/$sessionId", component: SessionPage });
const reportRoute = createRoute({ getParentRoute: () => appRoute, path: "runs/$runId", component: ReportPage });
const adminRoute = createRoute({ getParentRoute: () => appRoute, path: "admin", component: AdminPage });
const trashRoute = createRoute({ getParentRoute: () => appRoute, path: "trash", component: TrashPage });

const routeTree = rootRoute.addChildren([
  setupRoute,
  loginRoute,
  setPasswordRoute,
  appRoute.addChildren([homeRoute, projectsRoute, projectRoute, sessionRoute, reportRoute, adminRoute, trashRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
