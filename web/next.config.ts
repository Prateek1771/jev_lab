import type { NextConfig } from "next";

// The browser calls /api/*; Next proxies it to the Python API (api/main.py), so there is one origin and no CORS.
const API_URL = (process.env.JEV_API_URL ?? "http://127.0.0.1:8000").trim();

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
