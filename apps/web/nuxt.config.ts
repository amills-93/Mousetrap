export default defineNuxtConfig({
  compatibilityDate: "2026-11-01",
  devtools: { enabled: false },
  modules: ["@nuxtjs/tailwindcss"],
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    // Server-only; overridden at runtime by NUXT_* or read directly from process.env in server/lib.
    mlUrl: process.env.ML_URL || "http://localhost:8000",
    mlInternalKey: process.env.ML_INTERNAL_KEY || "",
    public: {
      demoMode: process.env.DEMO_MODE === "true",
    },
  },
  app: {
    head: { title: "Nimbus Mobile" },
  },
});
