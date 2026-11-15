// WebGL availability probe. MapLibre GL requires a WebGL context; some
// environments can't provide one (hardware acceleration disabled, locked-down
// or remote/virtual desktops, certain sandboxed browsers). In those cases
// `new maplibregl.Map(...)` throws synchronously during setupPainter, which
// otherwise escalates to the React error boundary and blanks the whole view.
// Callers use this to degrade gracefully instead.
export function isWebglAvailable() {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");
    return Boolean(gl && typeof gl.getParameter === "function");
  } catch {
    return false;
  }
}
