import type { NextConfig } from "next";

// The API base URL comes from NEXT_PUBLIC_API_URL at build time (see .env.example).
// Keep the local UI clean and avoid generated editor instruction files.
const nextConfig: NextConfig = {
  agentRules: false,
  devIndicators: false,
};

export default nextConfig;
