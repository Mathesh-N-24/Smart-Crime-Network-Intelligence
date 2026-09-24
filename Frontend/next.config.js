/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Air-gapped deployment: standalone output means the built app carries
  // its own node_modules subset and needs no network access to run.
  output: "standalone",
};

module.exports = nextConfig;
