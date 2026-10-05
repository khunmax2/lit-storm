// How to point an AI tool or a program at DeepLit's MCP server: one snippet per client, ready to copy,
// with the token filled in when there is one to fill in (docs/adr/0009).
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

const CLIENTS = ["claude-code", "claude-desktop", "cursor", "vscode", "curl", "python"] as const;
type Client = (typeof CLIENTS)[number];

const LABEL: Record<Client, string> = {
  "claude-code": "Claude Code",
  "claude-desktop": "Claude Desktop",
  cursor: "Cursor",
  vscode: "VS Code",
  curl: "curl",
  python: "Python",
};

export function snippet(client: Client, url: string, token: string) {
  const auth = `Bearer ${token}`;
  switch (client) {
    case "claude-code":
      return `claude mcp add --transport http deeplit ${url} \\\n  --header "Authorization: ${auth}"`;
    case "claude-desktop":
      // Its config file runs local programs; mcp-remote is the bridge to a server on the web. The header
      // goes through the environment: Claude Desktop on Windows splits arguments that hold a space.
      return JSON.stringify(
        {
          mcpServers: {
            deeplit: {
              command: "npx",
              args: ["-y", "mcp-remote", url, "--header", "Authorization:${AUTH_HEADER}"],
              env: { AUTH_HEADER: auth },
            },
          },
        },
        null,
        2,
      );
    case "cursor":
      return JSON.stringify({ mcpServers: { deeplit: { url, headers: { Authorization: auth } } } }, null, 2);
    case "vscode":
      return JSON.stringify({ servers: { deeplit: { type: "http", url, headers: { Authorization: auth } } } }, null, 2);
    case "curl":
      return [
        `curl -s ${url} \\`,
        `  -H "Authorization: ${auth}" \\`,
        `  -H "Content-Type: application/json" \\`,
        `  -H "Accept: application/json, text/event-stream" \\`,
        `  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`,
      ].join("\n");
    case "python":
      return [
        "# pip install mcp",
        "import asyncio",
        "from mcp import ClientSession",
        "from mcp.client.streamable_http import streamablehttp_client",
        "",
        `URL = "${url}"`,
        `HEADERS = {"Authorization": "${auth}"}`,
        "",
        "async def main():",
        "    async with streamablehttp_client(URL, headers=HEADERS) as (read, write, _):",
        "        async with ClientSession(read, write) as session:",
        "            await session.initialize()",
        '            started = await session.call_tool("research_start", {"topic": "Sodium-ion batteries", "language": "en"})',
        "            print(started.content[0].text)",
        "",
        "asyncio.run(main())",
      ].join("\n");
  }
}

export function McpSetup({ url, token, compact = false }: { url: string; token?: string; compact?: boolean }) {
  const { t } = useT();
  const [client, setClient] = useState<Client>("claude-code");
  const [copied, setCopied] = useState(false);
  const text = snippet(client, url, token ?? "<YOUR_TOKEN>");
  return (
    <section className={cn("grid min-w-0 gap-3", !compact && "rounded-xl border p-4")}>
      {!compact && (
        <div className="grid gap-1">
          <h2 className="text-sm font-medium">{t("connections.setup")}</h2>
          <p className="text-xs text-muted-foreground">{t("connections.setupLead")}</p>
          <code className="w-fit rounded bg-muted px-2 py-0.5 text-xs">{url}</code>
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {CLIENTS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => (setClient(c), setCopied(false))}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              c === client ? "border-brand/50 bg-brand-soft text-brand" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {LABEL[c]}
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{t(`connections.how.${client}` as Parameters<typeof t>[0])}</p>
      <div className="relative">
        <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/50 p-3 pr-20 text-xs leading-relaxed whitespace-pre">{text}</pre>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="absolute top-2 right-2"
          onClick={async () => {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            toast.success(t("copied"));
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? t("copied") : t("copy")}
        </Button>
      </div>
      {!token && <p className="text-xs text-muted-foreground">{t("connections.placeholder")}</p>}
    </section>
  );
}
