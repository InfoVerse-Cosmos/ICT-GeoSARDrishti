/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--ink) / <alpha-value>)",
        fg: "rgb(var(--fg) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        accent: "#2dd4bf",
        nasablue: "#0B3D91",
        nasared: "#FC3D21",
        isroblue: "#13388C",
        // NASA-ISRO telemetry palette (SRS §4.1)
        orbital: "#0B0F19", // deep orbital slate (canvas)
        panel: "#111827", // telemetry panel navy
        grid: "#1E293B", // subtle grid border
        nasa: "#0B3D91", // NASA mission blue
        cyan: "#38BDF8", // telemetry cyan (validated)
        isro: "#FF671F", // ISRO solar orange (playhead / accents)
        water: "#0284C7", // open water
        fveg: "#10B981", // flooded vegetation
        paddy: "#F59E0B", // paddy-like agricultural inundation
        alert: "#EF4444", // inspection candidate
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        float: { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        gradientMove: { "0%, 100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } },
      },
      animation: { float: "float 6s ease-in-out infinite", gradient: "gradientMove 8s ease infinite" },
    },
  },
  plugins: [],
};
