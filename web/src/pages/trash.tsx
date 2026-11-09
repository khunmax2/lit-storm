// The Trash: what the owner deleted, how long until it is gone, and a way back.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, FolderOpen, MessagesSquare, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, call } from "@/api/client";
import { LoadingRows, PageHeader, Toolbar, errorMessage, formatDate } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useT } from "@/i18n";

const KIND = {
  project: { label: "trash.kind.project", icon: FolderOpen },
  session: { label: "trash.kind.session", icon: MessagesSquare },
  run: { label: "trash.kind.run", icon: FileText },
} as const;

export function TrashPage() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const items = useQuery({ queryKey: ["trash"], queryFn: () => call(api.GET("/api/trash")) });
  const restore = useMutation({
    mutationFn: ({ kind, id }: { kind: string; id: string }) =>
      call(api.POST("/api/trash/{kind}/{item_id}/restore", { params: { path: { kind, item_id: id } } })),
    onSuccess: () => {
      toast.success(t("common.restored"));
      queryClient.invalidateQueries();
    },
    onError: (e) => toast.error(errorMessage(e, t)),
  });
  const daysLeft = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <Toolbar>
        <span className="text-sm font-medium">{t("trash.title")}</span>
      </Toolbar>
      <PageHeader title={t("trash.title")} description={t("trash.lead")} />
      {items.isLoading && <LoadingRows />}
      {items.data?.length === 0 && (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Trash2 />
            </EmptyMedia>
            <EmptyTitle>{t("trash.empty")}</EmptyTitle>
            <EmptyDescription>{t("trash.lead")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
      {!!items.data?.length && (
        <Card className="py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">{t("name")}</TableHead>
                <TableHead>{t("trash.deletedAt", { at: "" }).trim()}</TableHead>
                <TableHead />
                <TableHead className="pr-4" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.data.map((item) => {
                const kind = KIND[item.kind as keyof typeof KIND] ?? KIND.run;
                const Icon = kind.icon;
                const left = daysLeft(item.purge_at);
                return (
                  <TableRow key={`${item.kind}-${item.id}`}>
                    <TableCell className="max-w-0 pl-4">
                      <div className="flex items-center gap-3">
                        <Icon className="size-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                          <div className="truncate font-medium">{item.title}</div>
                          <div className="text-xs text-muted-foreground">{t(kind.label)}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(item.trashed_at, lang)}</TableCell>
                    <TableCell>
                      <Badge variant={left <= 3 ? "destructive" : "secondary"}>{t("trash.daysLeft", { n: left })}</Badge>
                    </TableCell>
                    <TableCell className="pr-4 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate({ kind: item.kind, id: item.id })}
                      >
                        <RotateCcw />
                        {t("trash.restore")}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
