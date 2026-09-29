// Ctrl/⌘ K: jump to a page, a topic or a project without leaving the keyboard.
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  FolderOpen,
  House,
  MessagesSquare,
  Settings,
  Trash2,
} from "lucide-react";
import { useEffect } from "react";

import { api, call, type Schemas } from "@/api/client";
import { DOT } from "@/components/app-sidebar";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useT } from "@/i18n";

export function SearchDialog({
  me,
  open,
  setOpen,
}: {
  me: Schemas["MeOut"];
  open: boolean;
  setOpen: (open: boolean) => void;
}) {
  const { t } = useT();
  const navigate = useNavigate();
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () =>
      call(
        api.GET("/api/sessions/recent", { params: { query: { limit: 12 } } }),
      ),
    enabled: open,
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => call(api.GET("/api/projects")),
    enabled: open,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(!open);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const go = (to: string, params?: Record<string, string>) => {
    setOpen(false);
    navigate({ to, params } as never);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title={t("search.label")}
      description={t("search.placeholder")}
      className="sm:max-w-xl"
    >
      <Command>
        <CommandInput placeholder={t("search.placeholder")} />
        <CommandList>
          <CommandEmpty>{t("search.empty")}</CommandEmpty>
          <CommandGroup heading={t("search.pages")}>
            <CommandItem onSelect={() => go("/")}>
              <House />
              {t("nav.homePage")}
            </CommandItem>
            <CommandItem onSelect={() => go("/projects")}>
              <FolderOpen />
              {t("nav.projects")}
            </CommandItem>
            <CommandItem onSelect={() => go("/trash")}>
              <Trash2 />
              {t("nav.trash")}
            </CommandItem>
            {me.role === "admin" && (
              <CommandItem onSelect={() => go("/admin")}>
                <Settings />
                {t("nav.admin")}
              </CommandItem>
            )}
          </CommandGroup>
          {!!recent.data?.length && (
            <>
              <CommandSeparator />
              <CommandGroup heading={t("nav.recent")}>
                {recent.data.map((s) => (
                  <CommandItem
                    key={s.id}
                    value={`${s.title} ${s.project_name} ${s.id}`}
                    onSelect={() =>
                      go("/sessions/$sessionId", { sessionId: s.id })
                    }
                  >
                    <MessagesSquare />
                    <span className="truncate">{s.title}</span>
                    <span className="ml-auto flex shrink-0 items-center gap-2 text-xs whitespace-nowrap text-muted-foreground">
                      {s.project_name}
                      <span
                        className={`size-1.5 rounded-full ${DOT[s.last_status ?? ""] ?? "bg-muted-foreground/40"}`}
                      />
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
          {!!projects.data?.length && (
            <>
              <CommandSeparator />
              <CommandGroup heading={t("nav.projects")}>
                {projects.data.map((p) => (
                  <CommandItem
                    key={p.id}
                    value={`${p.name} ${p.id}`}
                    onSelect={() =>
                      go("/projects/$projectId", { projectId: p.id })
                    }
                  >
                    <FolderOpen />
                    {p.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
