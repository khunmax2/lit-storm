// The Trash: what the owner deleted, how long until it is gone, and a way back.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, call } from "../api/client";
import { Button, ErrorText, PageTitle, Spinner, formatDate } from "../components/ui";
import { useT } from "../i18n";

const KIND = { project: "trash.kind.project", session: "trash.kind.session", run: "trash.kind.run" } as const;

export function TrashPage() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const items = useQuery({ queryKey: ["trash"], queryFn: () => call(api.GET("/api/trash")) });
  const restore = useMutation({
    mutationFn: ({ kind, id }: { kind: string; id: string }) =>
      call(api.POST("/api/trash/{kind}/{item_id}/restore", { params: { path: { kind, item_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const daysLeft = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));

  return (
    <>
      <PageTitle>{t("trash.title")}</PageTitle>
      <p className="mb-6 text-sm text-muted">{t("trash.lead")}</p>
      {items.isLoading && <Spinner />}
      {items.data?.length === 0 && <p className="text-muted">{t("trash.empty")}</p>}
      <ErrorText error={restore.error} />
      <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
        {items.data?.map((item) => (
          <li key={`${item.kind}-${item.id}`} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <div className="truncate font-medium">{item.title}</div>
              <div className="text-xs text-muted">
                {t(KIND[item.kind as keyof typeof KIND])} · {t("trash.deletedAt", { at: formatDate(item.trashed_at, lang) })} ·{" "}
                <span className={daysLeft(item.purge_at) <= 3 ? "text-bad" : ""}>
                  {t("trash.daysLeft", { n: daysLeft(item.purge_at) })}
                </span>
              </div>
            </div>
            <Button
              variant="quiet"
              disabled={restore.isPending}
              onClick={() => restore.mutate({ kind: item.kind, id: item.id })}
            >
              {t("trash.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </>
  );
}
