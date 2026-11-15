import type { NextConfig } from "next";

// The browser talks only to this origin; /api/* is proxied to FastAPI, so the session cookie
// stays first-party and the SSE stream needs no CORS.
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default config;
