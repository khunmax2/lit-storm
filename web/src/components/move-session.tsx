// Filing a topic: into a Project, into a new one, or out of any, as
// ChatGPT's "Move to project" and Claude's "Add to project" do.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderInput } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api, call } from "@/api/client";
import { ErrorText } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useT } from "@/i18n";

const NONE = "__none__";
const NEW = "__new__";

export function MoveSessionDialog({
  session,
  onOpenChange,
}: {
  /** The topic to move; the dialog is open while this is set. */
  session: { id: string; title: string; project_id: string | null } | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => call(api.GET("/api/projects")),
    enabled: !!session,
  });
  const [target, setTarget] = useState(NONE);
  const [name, setName] = useState("");
  useEffect(() => {
    if (session) {
      setTarget(session.project_id ?? NONE);
      setName("");
    }
  }, [session]);

  const move = useMutation({
    mutationFn: async () => {
      let project_id: string | null = target === NONE ? null : target;
      if (target === NEW) project_id = (await call(api.POST("/api/projects", { body: { name: name.trim() } }))).id;
      return call(
        api.PATCH("/api/sessions/{session_id}", {
          params: { path: { session_id: session!.id } },
          body: { project_id },
        }),
      );
    },
    onSuccess: (s) => {
      toast.success(s.project_name ? t("move.done", { name: s.project_name }) : t("move.doneNone"));
      queryClient.invalidateQueries();
      onOpenChange(false);
    },
  });
  const unchanged = target === (session?.project_id ?? NONE);

  return (
    <Dialog open={!!session} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            move.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("move.title")}</DialogTitle>
            <DialogDescription className="line-clamp-2">{session?.title}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="move-target">{t("home.project")}</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger id="move-target" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t("move.none")}</SelectItem>
                {!!projects.data?.length && <SelectSeparator />}
                {projects.data?.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
                <SelectSeparator />
                <SelectItem value={NEW}>{t("home.newProject")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {target === NEW && (
            <div className="grid gap-2">
              <Label htmlFor="move-name">{t("projects.name")}</Label>
              <Input
                id="move-name"
                autoFocus
                placeholder={t("projects.namePlaceholder")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          )}
          {move.error && <ErrorText error={move.error} />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={move.isPending || unchanged || (target === NEW && !name.trim())}>
              <FolderInput />
              {t("move.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
