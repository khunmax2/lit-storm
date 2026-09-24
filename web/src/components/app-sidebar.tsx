// The app shell's left rail: new research, the workspace, recent topics, and
// the account menu — the same layout people know from Perplexity and ChatGPT.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  BookOpenText,
  ChevronsUpDown,
  FolderOpen,
  Languages,
  LogOut,
  Monitor,
  Moon,
  Plus,
  Settings,
  Sun,
  Trash2,
} from "lucide-react";
import { useTheme } from "next-themes";

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
} from "@/components/ui/sidebar";
import { useT, type Lang } from "@/i18n";

const DOT: Record<string, string> = {
  running: "bg-brand animate-pulse",
  cancelling: "bg-warning animate-pulse",
  queued: "bg-muted-foreground/50",
  needs_selection: "bg-warning",
  failed: "bg-destructive",
  interrupted: "bg-destructive",
};

export function AppSidebar({ me }: { me: Schemas["MeOut"] }) {
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
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <BookOpenText className="size-4" />
                </div>
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">lit-storm</span>
                  <span className="truncate text-xs text-muted-foreground">{t("auth.tagline")}</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip={t("nav.home")} className="mt-2 border bg-background shadow-xs">
              <Link to="/">
                <Plus />
                <span>{t("nav.home")}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("nav.workspace")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={path.startsWith("/projects")} tooltip={t("nav.projects")}>
                  <Link to="/projects">
                    <FolderOpen />
                    <span>{t("nav.projects")}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={path === "/trash"} tooltip={t("nav.trash")}>
                  <Link to="/trash">
                    <Trash2 />
                    <span>{t("nav.trash")}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              {me.role === "admin" && (
                <SidebarMenuItem>
                  <SidebarMenuButton asChild isActive={path === "/admin"} tooltip={t("nav.admin")}>
                    <Link to="/admin">
                      <Settings />
                      <span>{t("nav.admin")}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>{t("nav.recent")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {recent.isLoading && Array.from({ length: 4 }, (_, i) => <SidebarMenuSkeleton key={i} />)}
              {recent.data?.length === 0 && (
                <p className="px-2 py-1 text-xs text-muted-foreground">{t("nav.noRecent")}</p>
              )}
              {recent.data?.map((s) => (
                <SidebarMenuItem key={s.id}>
                  <SidebarMenuButton asChild isActive={path === `/sessions/${s.id}`} className="h-auto py-1.5">
                    <Link to="/sessions/$sessionId" params={{ sessionId: s.id }}>
                      <span className="grid min-w-0 flex-1">
                        <span className="truncate">{s.title}</span>
                        <span className="truncate text-xs text-muted-foreground">{s.project_name}</span>
                      </span>
                      {s.last_status && DOT[s.last_status] && (
                        <span className={`size-2 shrink-0 rounded-full ${DOT[s.last_status]}`} />
                      )}
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg">{initials || "?"}</AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{me.name}</span>
                    <span className="truncate text-xs text-muted-foreground">{me.email}</span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4" />
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
