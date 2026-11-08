import { fileURLToPath } from "node:url";

export default defineNuxtConfig({
  compatibilityDate: "2026-11-01",
  devtools: { enabled: false },
  modules: ["@nuxtjs/tailwindcss"],
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    // Values here are build-time defaults. In Docker they are overridden at runtime by
    // NUXT_ML_URL, NUXT_ML_INTERNAL_KEY, NUXT_PUBLIC_DEMO_MODE (mapped in docker-compose.yml).
    mlUrl: process.env.ML_URL || "http://localhost:8000",
    mlInternalKey: process.env.ML_INTERNAL_KEY || "",
    public: {
      demoMode: process.env.DEMO_MODE === "true",
    },
  },
  app: {
    head: {
      title: "Nimbus Mobile",
      htmlAttrs: { lang: "en" },
      meta: [{ name: "theme-color", content: "#0E0F2E" }],
      link: [
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" },
        { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" },
      ],
    },
  },
  // Serve the built collector (zero-dependency ES modules) at /collector/* for non-Nuxt pages,
  // e.g. public/demo-vanilla.html loads /collector/adapters/vanilla.js.
  nitro: {
    publicAssets: [
      { dir: fileURLToPath(new URL("../../packages/collector/dist", import.meta.url)), baseURL: "/collector", maxAge: 300 },
    ],
  },
});
