import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#C8102E", dark: "#9B0C23" },
        bg: "var(--bg)",
        surface: "var(--surface)",
        muted: "var(--muted)",
        fg: "var(--fg)",
        line: "var(--line)",
      },
      screens: { sm: "640px", lg: "1024px", xl: "1280px" },
    },
  },
  plugins: [],
};

export default config;
