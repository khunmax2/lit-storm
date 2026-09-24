import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useNavigate,
} from "@tanstack/react-router";
import { useEffect } from "react";

import { ApiError, api, call } from "./api/client";
import { Spinner } from "./components/ui";
import { useT, type Lang } from "./i18n";
import { AdminPage } from "./pages/admin";
import { LoginPage, SetPasswordPage, SetupPage } from "./pages/auth";
import { ReportPage } from "./pages/report";
import { ProjectPage, ProjectsPage, SessionPage } from "./pages/research";
import { TrashPage } from "./pages/trash";

// Everything behind sign-in. Not signed in: the first-run setup page if the
// system has no Administrator yet, otherwise the sign-in page.
function SignedIn() {
  const { t, lang, setLang } = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
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

  const switchLang = useMutation({
    mutationFn: (l: Lang) => call(api.PUT("/api/me/language", { body: { ui_language: l } })),
    onSuccess: (m) => {
      setLang(m.ui_language as Lang);
      queryClient.setQueryData(["me"], m);
    },
  });
  const logout = useMutation({
    mutationFn: () => call(api.POST("/api/auth/logout")),
    onSettled: () => {
      queryClient.clear();
      navigate({ to: "/login" });
    },
  });

  if (!me.data) return <div className="p-8">{me.isLoading || unauthorised ? <Spinner /> : null}</div>;
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-5 px-4 py-3">
          <Link to="/" className="font-semibold tracking-tight">
            lit-storm
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link to="/" className="text-muted hover:text-ink [&.active]:text-ink" activeOptions={{ exact: true }}>
              {t("nav.projects")}
            </Link>
            <Link to="/trash" className="text-muted hover:text-ink [&.active]:text-ink">
              {t("nav.trash")}
            </Link>
            {me.data.role === "admin" && (
              <Link to="/admin" className="text-muted hover:text-ink [&.active]:text-ink">
                {t("nav.admin")}
              </Link>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-4 text-sm">
            <button className="text-muted hover:text-ink" onClick={() => switchLang.mutate(lang === "th" ? "en" : "th")}>
              {lang === "th" ? "EN" : "ไทย"}
            </button>
            <span className="hidden text-muted sm:inline">{me.data.name}</span>
            <button className="text-muted hover:text-ink" onClick={() => logout.mutate()}>
              {t("signOut")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

const rootRoute = createRootRoute({ component: Outlet });

const setupRoute = createRoute({ getParentRoute: () => rootRoute, path: "setup", component: SetupPage });
const loginRoute = createRoute({ getParentRoute: () => rootRoute, path: "login", component: LoginPage });
const setPasswordRoute = createRoute({ getParentRoute: () => rootRoute, path: "set-password", component: SetPasswordPage });

const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: SignedIn });
const projectsRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: ProjectsPage });
const projectRoute = createRoute({ getParentRoute: () => appRoute, path: "projects/$projectId", component: ProjectPage });
const sessionRoute = createRoute({ getParentRoute: () => appRoute, path: "sessions/$sessionId", component: SessionPage });
const reportRoute = createRoute({ getParentRoute: () => appRoute, path: "runs/$runId", component: ReportPage });
const adminRoute = createRoute({ getParentRoute: () => appRoute, path: "admin", component: AdminPage });
const trashRoute = createRoute({ getParentRoute: () => appRoute, path: "trash", component: TrashPage });

const routeTree = rootRoute.addChildren([
  setupRoute,
  loginRoute,
  setPasswordRoute,
  appRoute.addChildren([projectsRoute, projectRoute, sessionRoute, reportRoute, adminRoute, trashRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
