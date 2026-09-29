// The API client, typed from FastAPI's OpenAPI (`npm run api` regenerates it).
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

function cookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

// Every change carries the session's CSRF token (docs/adr/0002).
const csrf: Middleware = {
  onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      const token = cookie("litstorm_csrf");
      if (token) request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: "" });
api.use(csrf);

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

// openapi-fetch returns {data, error}; pages would rather throw.
export async function call<T>(promise: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    throw new ApiError(response.status, typeof detail === "string" ? detail : "error");
  }
  return data as T;
}
