// How to point an AI tool or a program at DeepLit's MCP servers: the combined one or one mode's, then one
// snippet per client, ready to copy, with the token filled in when there is one to fill in (docs/adr/0009).
import { Check, Copy, Loader2, PlugZap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BASE, type Schemas } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

const CLIENTS = ["claude-code", "claude-desktop", "cursor", "vscode", "curl", "python"] as const;
type Client = (typeof CLIENTS)[number];

type Endpoint = Schemas["EndpointOut"];

const LABEL: Record<Client, string> = {
  "claude-code": "Claude Code",
  "claude-desktop": "Claude Desktop",
  cursor: "Cursor",
  vscode: "VS Code",
  curl: "curl",
  python: "Python",
};

export function snippet(client: Client, endpoint: Pick<Endpoint, "name" | "url" | "tool_prefix">, token: string) {
  const { name, url } = endpoint;
  const auth = `Bearer ${token}`;
  switch (client) {
    case "claude-code":
      return `claude mcp add --transport http ${name} ${url} \\\n  --header "Authorization: ${auth}"`;
    case "claude-desktop":
      // Its config file runs local programs; mcp-remote is the bridge to a server on the web. The header
      // goes through the environment: Claude Desktop on Windows splits arguments that hold a space.
      return JSON.stringify(
        {
          mcpServers: {
            [name]: {
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
      return JSON.stringify({ mcpServers: { [name]: { url, headers: { Authorization: auth } } } }, null, 2);
    case "vscode":
      return JSON.stringify({ servers: { [name]: { type: "http", url, headers: { Authorization: auth } } } }, null, 2);
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
        "# pip install mcp httpx",
        "import asyncio",
        "import httpx",
        "from mcp import ClientSession",
        "from mcp.client.streamable_http import streamable_http_client",
        "",
        `URL = "${url}"`,
        `HEADERS = {"Authorization": "${auth}"}`,
        "",
        "async def main():",
        "    async with httpx.AsyncClient(headers=HEADERS, timeout=120) as http:",
        "        async with streamable_http_client(URL, http_client=http) as (read, write, _):",
        "            async with ClientSession(read, write) as session:",
        "                await session.initialize()",
        `                started = await session.call_tool("${endpoint.tool_prefix}_start", {"topic": "Sodium-ion batteries", "language": "en"})`,
        "                print(started.content[0].text)",
        "",
        "asyncio.run(main())",
      ].join("\n");
  }
}

/** Call the endpoint's options tool with the token, as a client would, and say what came back. */
async function tryToken(token: string, endpoint: Endpoint) {
  const r = await fetch(`${BASE}${endpoint.path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: `${endpoint.tool_prefix}_options`, arguments: {} },
    }),
  });
  const text = await r.text();
  if (!r.ok) {
    let why = `HTTP ${r.status}`;
    try {
      why = JSON.parse(text).message || why;
    } catch {
      // Not JSON: the status says enough.
    }
    throw new Error(why);
  }
  // A Streamable HTTP answer: server-sent events, the message on a data line.
  const line = text.split(/\r?\n/).find((l) => l.startsWith("data: "));
  const message = JSON.parse(line ? line.slice(6) : text);
  if (message.error) throw new Error(message.error.message);
  const result = message.result;
  if (result.isError) throw new Error(result.content?.[0]?.text ?? "error");
  const options = result.structuredContent?.result ?? result.structuredContent ?? JSON.parse(result.content[0].text);
  return { modes: options.engines.length as number, left: options.quota.remaining as number };
}

function TestConnection({ token, endpoint }: { token: string; endpoint: Endpoint }) {
  const { t } = useT();
  const [state, setState] = useState<{ busy?: boolean; ok?: boolean; text?: string; on?: string }>({});
  const shown = state.on === endpoint.id ? state : {};
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={shown.busy}
        onClick={async () => {
          const on = endpoint.id;
          setState({ busy: true, on });
          try {
            const got = await tryToken(token, endpoint);
            const text =
              on === "all"
                ? t("connections.testOk", got)
                : t("connections.testOkMode", { mode: t(`connections.ep.${on}` as Key), left: got.left });
            setState({ ok: true, text, on });
          } catch (error) {
            setState({ ok: false, text: t("connections.testFail", { why: (error as Error).message }), on });
          }
        }}
      >
        {shown.busy ? <Loader2 className="animate-spin" /> : <PlugZap />}
        {shown.busy ? t("connections.testing") : t("connections.test")}
      </Button>
      {shown.text && <span className={cn("text-xs", shown.ok ? "text-success" : "text-destructive")}>{shown.text}</span>}
    </div>
  );
}

/** Which server: the combined one, or one mode's, each with what it is good for. */
function EndpointPicker({
  endpoints,
  value,
  onChange,
  narrow,
}: {
  endpoints: Endpoint[];
  value: string;
  onChange: (id: string) => void;
  narrow: boolean;
}) {
  const { t } = useT();
  return (
    <div className="grid gap-1.5">
      <p className="text-xs font-medium">{t("connections.endpoint")}</p>
      <div className={cn("grid grid-cols-2 gap-2", !narrow && "lg:grid-cols-3")}>
        {endpoints.map((e) => (
          <button
            key={e.id}
            type="button"
            disabled={!e.allowed}
            title={e.allowed ? undefined : t("connections.epNotAllowed")}
            onClick={() => onChange(e.id)}
            className={cn(
              "grid content-start gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-45",
              e.id === value ? "border-brand/50 bg-brand-soft" : "hover:bg-muted/60",
            )}
          >
            <span className={cn("text-xs font-medium", e.id === value && "text-brand")}>{t(`connections.ep.${e.id}` as Key)}</span>
            <span className="text-[11px] leading-snug text-muted-foreground">
              {e.allowed ? t(`connections.epAbout.${e.id}` as Key) : t("connections.epNotAllowed")}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function McpSetup({ endpoints, token, compact = false }: { endpoints: Endpoint[]; token?: string; compact?: boolean }) {
  const { t } = useT();
  const [client, setClient] = useState<Client>("claude-code");
  const [picked, setPicked] = useState("all");
  const [copied, setCopied] = useState(false);
  const endpoint = endpoints.find((e) => e.id === picked && e.allowed) ?? endpoints[0];
  const text = snippet(client, endpoint, token ?? "<YOUR_TOKEN>");
  return (
    <section className={cn("grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3", !compact && "rounded-xl border p-4")}>
      {!compact && (
        <div className="grid gap-1">
          <h2 className="text-sm font-medium">{t("connections.setup")}</h2>
          <p className="text-xs text-muted-foreground">{t("connections.setupLead")}</p>
        </div>
      )}
      <EndpointPicker
        endpoints={endpoints}
        value={endpoint.id}
        onChange={(id) => (setPicked(id), setCopied(false))}
        narrow={compact}
      />
      <code className="w-fit max-w-full truncate rounded bg-muted px-2 py-0.5 text-xs">{endpoint.url}</code>
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
      {token ? <TestConnection token={token} endpoint={endpoint} /> : <p className="text-xs text-muted-foreground">{t("connections.placeholder")}</p>}
    </section>
  );
}
