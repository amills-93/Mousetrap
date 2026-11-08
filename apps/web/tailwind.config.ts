import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

// Nimbus design tokens. Indigo is the brand; cyan is a sparing accent (mostly on the dark shell);
// ink is the dark shell and hero surfaces. Status colors come from Tailwind's palette.
export default {
  content: [],
  theme: {
    extend: {
      colors: {
        nimbus: {
          DEFAULT: "#2B2D7C",
          50: "#EEF0FF",
          100: "#E0E3FA",
          200: "#C6CAF0",
          300: "#A9ADD6",
          400: "#7F84C4",
          500: "#4E52A8",
          600: "#3A3D96",
          700: "#2B2D7C",
          800: "#1C1D5A",
          900: "#16174A",
          950: "#0E0F2E",
          accent: "#22C3E6",
        },
        ink: {
          DEFAULT: "#0F1030",
          muted: "#5B5F8A",
          soft: "#3B3F6B",
          line: "#E4E6F2",
          wash: "#F4F5FA",
        },
      },
      fontFamily: {
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
        display: ['"Space Grotesk"', "Inter", ...defaultTheme.fontFamily.sans],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,16,48,0.04), 0 1px 1px rgba(15,16,48,0.02)",
        lift: "0 1px 2px rgba(15,16,48,0.06), 0 8px 24px -12px rgba(15,16,48,0.18)",
        hero: "0 1px 2px rgba(15,16,48,0.2), 0 16px 40px -16px rgba(22,23,74,0.6)",
        modal: "0 24px 64px -16px rgba(14,15,46,0.6)",
        focus: "0 0 0 4px rgba(43,45,124,0.14)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "pop-in": { from: { opacity: "0", transform: "translateY(8px) scale(0.98)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        "fade-in": "fade-in 150ms ease-out",
        "pop-in": "pop-in 200ms cubic-bezier(0.2, 0.8, 0.2, 1)",
      },
    },
  },
} satisfies Partial<Config>;
