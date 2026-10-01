import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, createRootRoute, createRoute, createRouter, redirect, useNavigate } from "@tanstack/react-router";
import { Loader2, Moon, Plus, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { ApiError, api, call } from "@/api/client";
import { AppSidebar } from "@/components/app-sidebar";
import { SearchDialog } from "@/components/search-dialog";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { useT, type Lang } from "@/i18n";
import { AdminPage } from "@/pages/admin";
import { LoginPage, SetPasswordPage, SetupPage } from "@/pages/auth";
import { HomePage } from "@/pages/home";
import { ReportPage } from "@/pages/report";
import { AllResearchPage, ProjectPage, ProjectsPage, SessionPage } from "@/pages/research";
import { TrashPage } from "@/pages/trash";

// The bar over every page: new research on the left, then whatever the page
// puts in its toolbar, and the theme switch on the right.
function Header() {
  const { t, lang, setLang } = useT();
  const { state, isMobile } = useSidebar();
  const { resolvedTheme, setTheme } = useTheme();
  const client = useQueryClient();
  // The interface language, one press away, kept with the account as the
  // account menu keeps it; it changes at once and goes back if not saved.
  const other: Lang = lang === "th" ? "en" : "th";
  const switchLang = useMutation({
    mutationFn: (l: Lang) => call(api.PUT("/api/me/language", { body: { ui_language: l } })),
    onMutate: (l) => {
      const before = lang;
      setLang(l);
      return before;
    },
    onSuccess: (m) => client.setQueryData(["me"], m),
    onError: (_e, _l, before) => before && setLang(before),
  });
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur">
      {(isMobile || state === "collapsed") && <SidebarTrigger className="size-9 rounded-lg border shadow-xs" />}
      <Button variant="outline" className="h-9 rounded-lg shadow-xs" asChild>
        <Link to="/">
          <Plus />
          <span className="hidden sm:inline">{t("nav.home")}</span>
        </Link>
      </Button>
      <div id="page-toolbar" className="flex min-w-0 flex-1 items-center gap-2 pl-1" />
      <Button
        variant="outline"
        size="icon"
        className="size-9 rounded-lg text-xs font-semibold tracking-wide shadow-xs"
        aria-label={t("lang.switch")}
        title={t("lang.switch")}
        disabled={switchLang.isPending}
        onClick={() => switchLang.mutate(other)}
      >
        {lang === "th" ? "TH" : "EN"}
      </Button>
      <Button
        variant="outline"
        size="icon"
        className="size-9 rounded-lg shadow-xs"
        aria-label={t("theme.label")}
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        {resolvedTheme === "dark" ? <Sun /> : <Moon />}
      </Button>
    </header>
  );
}

// Everything behind sign-in. Not signed in: the first-run setup page if the
// system has no Administrator yet, otherwise the sign-in page.
function SignedIn() {
  const { lang, setLang } = useT();
  const navigate = useNavigate();
  const [searching, setSearching] = useState(false);
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
      <AppSidebar me={me.data} onSearch={() => setSearching(true)} />
      {/* min-w-0: a wide table scrolls inside its card instead of widening the page. */}
      <SidebarInset className="min-w-0">
        <Header />
        <Outlet />
      </SidebarInset>
      <SearchDialog me={me.data} open={searching} setOpen={setSearching} />
    </SidebarProvider>
  );
}

const rootRoute = createRootRoute({ component: Outlet });

const setupRoute = createRoute({ getParentRoute: () => rootRoute, path: "setup", component: SetupPage });
const loginRoute = createRoute({ getParentRoute: () => rootRoute, path: "login", component: LoginPage });
const setPasswordRoute = createRoute({ getParentRoute: () => rootRoute, path: "set-password", component: SetPasswordPage });

const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: SignedIn });
const homeRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: HomePage });
const allResearchRoute = createRoute({ getParentRoute: () => appRoute, path: "research", component: AllResearchPage });
const projectsRoute = createRoute({ getParentRoute: () => appRoute, path: "projects", component: ProjectsPage });
const projectRoute = createRoute({ getParentRoute: () => appRoute, path: "projects/$projectId", component: ProjectPage });
const sessionRoute = createRoute({ getParentRoute: () => appRoute, path: "sessions/$sessionId", component: SessionPage });
const reportRoute = createRoute({ getParentRoute: () => appRoute, path: "runs/$runId", component: ReportPage });
const settingsRoute = createRoute({ getParentRoute: () => appRoute, path: "settings/$section", component: AdminPage });
// The old address of the settings, kept for links people saved.
const adminRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "admin",
  beforeLoad: () => {
    throw redirect({ to: "/settings/$section", params: { section: "users" } });
  },
});
const trashRoute = createRoute({ getParentRoute: () => appRoute, path: "trash", component: TrashPage });

const routeTree = rootRoute.addChildren([
  setupRoute,
  loginRoute,
  setPasswordRoute,
  appRoute.addChildren([homeRoute, allResearchRoute, projectsRoute, projectRoute, sessionRoute, reportRoute, settingsRoute, adminRoute, trashRoute]),
]);

export const router = createRouter({ routeTree, basepath: import.meta.env.BASE_URL });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
