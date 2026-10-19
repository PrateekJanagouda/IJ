import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the production container (deploy/Dockerfile).
  output: "standalone",
  // Django routes end in "/"; don't let Next strip it and redirect.
  skipTrailingSlashRedirect: true,
  // Same-origin proxy: the browser only ever talks to this app, so Django's session and
  // CSRF cookies work without CORS and no token ever lives in JavaScript-readable storage.
  async rewrites() {
    // `:path*` never includes the trailing slash, so add it back (query strings pass through).
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*/` }];
  },
  // The artist-first app (public/equra.html) is the front door; the older pages stay reachable.
  async redirects() {
    return [{ source: "/", destination: "/equra.html", permanent: false }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
