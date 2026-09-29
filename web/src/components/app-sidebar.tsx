// The app shell's left rail: the brand, search, the workspace, recent topics,
// and the account card at the foot.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  BookOpenText,
  ChevronsUpDown,
  FolderOpen,
  House,
  Languages,
  Library,
  LogOut,
  Monitor,
  Moon,
  Search,
  Settings,
  Sun,
  Trash2,
} from "lucide-react";
import { useTheme } from "next-themes";
import type { ReactNode } from "react";

import { api, call, type Schemas } from "@/api/client";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Kbd } from "@/components/ui/kbd";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useT, type Lang } from "@/i18n";

export const DOT: Record<string, string> = {
  succeeded: "bg-success",
  running: "bg-brand animate-pulse",
  cancelling: "bg-warning animate-pulse",
  queued: "bg-muted-foreground/50",
  needs_selection: "bg-warning",
  failed: "bg-destructive",
  interrupted: "bg-destructive",
  cancelled: "bg-muted-foreground/40",
};

// The page you are on sits on a raised white card, as in the design reference.
const ITEM =
  "h-9 text-sidebar-foreground/80 data-[active=true]:bg-background data-[active=true]:font-medium " +
  "data-[active=true]:text-sidebar-foreground data-[active=true]:shadow-xs data-[active=true]:ring-1 " +
  "data-[active=true]:ring-sidebar-border";

function NavItem({ to, icon, label, active }: { to: string; icon: ReactNode; label: string; active: boolean }) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={label} className={ITEM}>
        <Link to={to}>
          {icon}
          <span>{label}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export function AppSidebar({ me, onSearch }: { me: Schemas["MeOut"]; onSearch: () => void }) {
  const { t, lang, setLang } = useT();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => call(api.GET("/api/sessions/recent", { params: { query: { limit: 12 } } })),
    refetchInterval: 15000,
  });
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
  const initials = me.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-3 p-3">
        <div className="flex items-center gap-2.5 group-data-[collapsible=icon]:justify-center">
          <Link to="/" className="flex min-w-0 flex-1 items-center gap-2.5 group-data-[collapsible=icon]:flex-none">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <BookOpenText className="size-4" />
            </div>
            <span className="truncate text-lg font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
              lit-storm
            </span>
          </Link>
          <SidebarTrigger className="text-muted-foreground group-data-[collapsible=icon]:hidden" />
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={onSearch}
              tooltip={t("search.label")}
              className="h-9 border bg-background text-muted-foreground shadow-xs hover:bg-background hover:text-foreground"
            >
              <Search />
              <span className="flex-1">{t("search.placeholder")}</span>
              <Kbd className="group-data-[collapsible=icon]:hidden">{isMac ? "⌘ K" : "Ctrl K"}</Kbd>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarSeparator className="mx-3" />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <NavItem to="/" icon={<House />} label={t("nav.homePage")} active={path === "/"} />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="pt-0">
          <SidebarGroupLabel className="uppercase tracking-wide">{t("nav.research")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <NavItem
                to="/research"
                icon={<Library />}
                label={t("nav.allResearch")}
                active={path === "/research"}
              />
              <NavItem
                to="/projects"
                icon={<FolderOpen />}
                label={t("nav.projects")}
                active={path.startsWith("/projects")}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="mx-3" />

        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel className="uppercase tracking-wide">{t("nav.recent")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {recent.isLoading && Array.from({ length: 4 }, (_, i) => <SidebarMenuSkeleton key={i} />)}
              {recent.data?.length === 0 && (
                <p className="px-2 py-1 text-xs text-muted-foreground">{t("nav.noRecent")}</p>
              )}
              {recent.data?.slice(0, 8).map((s) => (
                <SidebarMenuItem key={s.id}>
                  <SidebarMenuButton asChild isActive={path === `/sessions/${s.id}`} className={ITEM}>
                    <Link to="/sessions/$sessionId" params={{ sessionId: s.id }}>
                      <span
                        className={`ml-1 size-1.5 shrink-0 rounded-full ${DOT[s.last_status ?? ""] ?? "bg-muted-foreground/40"}`}
                      />
                      <span className="truncate">{s.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="gap-3 p-3">
        <SidebarMenu>
          <NavItem to="/trash" icon={<Trash2 />} label={t("nav.trash")} active={path === "/trash"} />
          {me.role === "admin" && (
            <NavItem
              to="/settings/users"
              icon={<Settings />}
              label={t("nav.admin")}
              active={path.startsWith("/settings")}
            />
          )}
        </SidebarMenu>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="h-14 border bg-background shadow-xs data-[state=open]:bg-background group-data-[collapsible=icon]:border-0 group-data-[collapsible=icon]:shadow-none"
                >
                  <Avatar className="size-9 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-brand-soft text-brand">{initials || "?"}</AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{me.name}</span>
                    <span className="truncate text-xs text-muted-foreground">{me.email}</span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-(--radix-dropdown-menu-trigger-width) min-w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="text-sm font-medium">{me.name}</div>
                  <div className="text-xs text-muted-foreground">{me.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Languages />
                    {t("lang.label")}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuRadioGroup value={lang} onValueChange={(v) => switchLang.mutate(v as Lang)}>
                      <DropdownMenuRadioItem value="th">ไทย</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="en">English</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    {theme === "dark" ? <Moon /> : theme === "light" ? <Sun /> : <Monitor />}
                    {t("theme.label")}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuRadioGroup value={theme ?? "system"} onValueChange={setTheme}>
                      <DropdownMenuRadioItem value="light">{t("theme.light")}</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="dark">{t("theme.dark")}</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="system">{t("theme.system")}</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => logout.mutate()}>
                  <LogOut />
                  {t("signOut")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
