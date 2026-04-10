/** @type {import('next').NextConfig} */
const nextConfig = {
  // Use "standalone" only when building Docker images (set via env).
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
};

export default nextConfig;
