// System status: for Administrators, its own place in the sidebar above the settings.
import { Toolbar } from "@/components/common";
import { SystemStatus } from "@/components/system-status";
import { useT } from "@/i18n";

export function StatusPage() {
  const { t } = useT();
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <Toolbar>
        <span className="text-sm font-medium">{t("admin.status")}</span>
      </Toolbar>
      <SystemStatus />
    </div>
  );
}
