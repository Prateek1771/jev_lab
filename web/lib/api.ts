import type { ProjectDetail, ProjectSummary } from "./types";

// Server components call the Python API directly; the browser goes through the /api rewrite (next.config.ts).
export const API_URL = process.env.JEV_API_URL ?? "http://127.0.0.1:8000";

async function server<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export const getProjects = () => server<ProjectSummary[]>("/api/projects");
export const getProject = (nn: string) => server<ProjectDetail>(`/api/projects/${nn}`);

/** The paid POSTs (run, dataset) go straight to the API when deployed: its rate limit then sees the visitor's IP,
    not Vercel's, and no proxy cuts a long dataset stream. Empty (local) = the /api rewrite. */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Browser-side JSON fetch; an API error body ({"error": ...}) becomes the thrown message. */
export async function client<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ?? body.detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}
