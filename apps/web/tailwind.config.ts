import type { Config } from "tailwindcss";

export default {
  content: [],
  theme: {
    extend: {
      colors: {
        nimbus: {
          DEFAULT: "#2B2D7C", // deep indigo primary
          accent: "#22C3E6",  // cyan accent
        },
      },
    },
  },
} satisfies Partial<Config>;
