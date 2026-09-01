import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "media",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark, Telegram-inspired palette (not a copy).
        bg: {
          DEFAULT: "#1e293b",
          panel: "#172033",
          deeper: "#0f172a",
        },
        surface: {
          DEFAULT: "#26334d",
          hover: "#33415c",
        },
        ac: {
          DEFAULT: "#2b8a4e",
          muted: "#8b5cf6",
        },
        text: {
          DEFAULT: "#e2e8f0",
          muted: "#94a3b8",
          faint: "#64748b",
        },
      },
      spacing: {
        "2xs": "4px",
      },
    },
  },
};

export default config;