// A Project's settings (docs/web-app-design.md, รุ่นสอง: โครงร่างที่ผู้ใช้
// กำหนดและ Project): what research started in it begins with, and its two
// instructions — what to search for, and how to write. Runs already made
// keep what they were started with.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, call, type Schemas } from "@/api/client";
import { ErrorText } from "@/components/common";
import { useRunOptions } from "@/components/composer";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useT } from "@/i18n";

type Project = Schemas["ProjectOut"];
const NONE = "none";

function Row({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Pick({
  id,
  value,
  onChange,
  items,
}: {
  id: string;
  value: string | null | undefined;
  onChange: (v: string | null) => void;
  items: { value: string; label: string }[];
}) {
  const { t } = useT();
  return (
    <Select value={value ?? NONE} onValueChange={(v) => onChange(v === NONE ? null : v)}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>{t("projectSettings.systemDefault")}</SelectItem>
        {items.map((i) => (
          <SelectItem key={i.value} value={i.value}>
            {i.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ProjectSettingsDialog({ project, open, onOpenChange }: { project: Project; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const o = useRunOptions().data;
  const [name, setName] = useState(project.name);
  const [defaults, setDefaults] = useState(project.defaults);
  const [sectionsText, setSectionsText] = useState("");
  const [scope, setScope] = useState("");
  const [style, setStyle] = useState("");
  useEffect(() => {
    if (!open) return;
    setName(project.name);
    setDefaults(project.defaults);
    setSectionsText((project.defaults.sections ?? []).join("\n"));
    setScope(project.search_scope ?? "");
    setStyle(project.writing_style ?? "");
  }, [open, project]);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/projects/{project_id}", {
          params: { path: { project_id: project.id } },
          body: {
            name: name.trim() || project.name,
            defaults: { ...defaults, sections: sectionsText.split("\n").filter((l) => l.trim()) },
            search_scope: scope,
            writing_style: style,
          },
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(t("common.saved"));
      onOpenChange(false);
    },
  });
  const set = (patch: Partial<Project["defaults"]>) => setDefaults({ ...defaults, ...patch });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 p-0 sm:max-w-2xl">
        <form
          className="flex max-h-[90svh] flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <DialogHeader className="border-b px-6 pt-6 pb-4">
            <DialogTitle>{t("projectSettings.title")}</DialogTitle>
            <DialogDescription>{t("projectSettings.lead")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-6 overflow-y-auto px-6 py-5">
            <Row id="ps-name" label={t("projects.name")}>
              <Input id="ps-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
            </Row>

            <fieldset className="grid gap-4">
              <legend className="mb-1 text-sm font-medium">{t("projectSettings.defaults")}</legend>
              <p className="-mt-2 text-xs text-muted-foreground">{t("projectSettings.defaultsLead")}</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Row id="ps-lang" label={t("run.language")}>
                  <Pick
                    id="ps-lang"
                    value={defaults.language}
                    onChange={(v) => set({ language: v as "th" | "en" | null })}
                    items={[
                      { value: "th", label: t("lang.th") },
                      { value: "en", label: t("lang.en") },
                    ]}
                  />
                </Row>
                <Row id="ps-depth" label={t("depth.label")}>
                  <Pick
                    id="ps-depth"
                    value={defaults.depth}
                    onChange={(v) => set({ depth: v as "fast" | "standard" | "deep" | null })}
                    items={(["fast", "standard", "deep"] as const).map((d) => ({ value: d, label: t(`depth.${d}`) }))}
                  />
                </Row>
                <Row id="ps-model" label={t("run.model")}>
                  <Pick
                    id="ps-model"
                    value={defaults.llm_model_id}
                    onChange={(v) => set({ llm_model_id: v })}
                    items={(o?.models ?? []).map((m) => ({ value: m.id, label: m.label }))}
                  />
                </Row>
                <Row id="ps-search" label={t("run.search")}>
                  <Pick
                    id="ps-search"
                    value={defaults.search_provider_id}
                    onChange={(v) => set({ search_provider_id: v })}
                    items={(o?.search_providers ?? []).map((p) => ({ value: p.id, label: p.label }))}
                  />
                </Row>
              </div>
              <Row id="ps-sections" label={t("sections.title")} hint={t("projectSettings.sectionsHint")}>
                <Textarea
                  id="ps-sections"
                  value={sectionsText}
                  onChange={(e) => setSectionsText(e.target.value)}
                  placeholder={t("sections.placeholder")}
                  className="min-h-20"
                />
              </Row>
            </fieldset>

            <fieldset className="grid gap-4">
              <legend className="mb-1 text-sm font-medium">{t("projectSettings.instructions")}</legend>
              <p className="-mt-2 text-xs text-muted-foreground">{t("projectSettings.instructionsLead")}</p>
              <Row id="ps-scope" label={t("projectSettings.scope")} hint={t("projectSettings.scopeHint")}>
                <Textarea id="ps-scope" value={scope} onChange={(e) => setScope(e.target.value)} maxLength={2000} className="min-h-20" />
              </Row>
              <Row id="ps-style" label={t("projectSettings.style")} hint={t("projectSettings.styleHint")}>
                <Textarea id="ps-style" value={style} onChange={(e) => setStyle(e.target.value)} maxLength={2000} className="min-h-20" />
              </Row>
            </fieldset>
            {save.error && <ErrorText error={save.error} />}
          </div>
          <DialogFooter className="border-t px-6 py-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
