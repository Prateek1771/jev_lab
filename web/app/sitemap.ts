import type { MetadataRoute } from "next";
import { getProjects } from "@/lib/api";
import { SITE_URL } from "@/lib/site";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // API down (Render cold start) → still list the 25 experiments rather than 500
  const ids = await getProjects()
    .then((ps) => ps.map((p) => p.id))
    .catch(() => Array.from({ length: 25 }, (_, i) => String(i + 1).padStart(2, "0")));
  return [
    { url: SITE_URL, priority: 1 },
    { url: `${SITE_URL}/jev`, priority: 0.8 },
    ...ids.map((id) => ({ url: `${SITE_URL}/p/${id}`, priority: 0.7 })),
  ];
}
