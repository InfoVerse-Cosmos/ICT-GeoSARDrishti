/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
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
    },
  },
  plugins: [],
};
