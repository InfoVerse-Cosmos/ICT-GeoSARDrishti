import { useEffect, useRef, useState } from 'react';

// A sphere projected directly in a fragment shader; no additional 3D library.
const VERTEX = `
  attribute vec2 position;
  varying vec2 point;
  void main() { point = position; gl_Position = vec4(position, 0.0, 1.0); }
`;
const FRAGMENT = `
  precision mediump float;
  varying vec2 point;
  uniform sampler2D earth;
  uniform float rotation;
  const float PI = 3.14159265359;
  void main() {
    vec2 p = point * 1.08;
    float radius = length(p);
    if (radius > 1.0) {
      // Truly transparent outside the planet: no rectangular canvas backdrop.
      gl_FragColor = vec4(0.0);
      return;
    }
    vec3 normal = vec3(p, sqrt(max(0.0, 1.0 - dot(p, p))));
    // Tilt the axis, then rotate longitude to reveal every continent.
    float tilt = 0.18;
    vec3 surface = vec3(cos(tilt)*normal.x + sin(tilt)*normal.y,
                       -sin(tilt)*normal.x + cos(tilt)*normal.y, normal.z);
    vec2 uv = vec2(fract(0.5 + atan(surface.x, surface.z)/(2.0*PI) + rotation),
                   0.5 - asin(clamp(surface.y, -1.0, 1.0))/PI);
    vec3 color = texture2D(earth, uv).rgb;
    float light = max(dot(normal, normalize(vec3(-0.7, 0.4, 1.3))), 0.0);
    color *= 0.22 + 0.88 * light;
    float rim = pow(1.0 - normal.z, 3.0);
    color += vec3(0.36, 0.36, 0.35) * rim * 0.48;
    gl_FragColor = vec4(color, 1.0 - smoothstep(0.995, 1.0, radius));
  }
`;

export default function RotatingEarth() {
  const canvasRef = useRef(null);
  const satelliteRef = useRef(null);
  const runningRef = useRef(false);
  const hoveredRef = useRef(false);
  const [running, setRunning] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setRunning(!media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => { runningRef.current = running; }, [running]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false, antialias: false });
    if (!gl) return; // Keep the existing photograph when WebGL is unavailable.
    let frame = 0;
    let disposed = false;
    let visible = true;
    let rotation = 0.18; // Start with Africa / the Indian Ocean in view.
    let orbit = -0.65;
    let previousTime = 0;
    let lastDrawnRotation = null;
    const resources = [];
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      resources.push(() => gl.deleteShader(shader));
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error('Globe shader unavailable');
      return shader;
    };
    let program;
    try {
      program = gl.createProgram();
      resources.push(() => gl.deleteProgram(program));
      gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Globe program unavailable');
    } catch {
      resources.reverse().forEach(release => release());
      return;
    }
    gl.useProgram(program);
    gl.clearColor(0, 0, 0, 0);
    const buffer = gl.createBuffer();
    resources.push(() => gl.deleteBuffer(buffer));
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const angle = gl.getUniformLocation(program, 'rotation');
    const texture = gl.createTexture();
    resources.push(() => gl.deleteTexture(texture));
    const image = new Image();

    const draw = time => {
      if (disposed || gl.isContextLost()) return;
      if (visible && !document.hidden) {
        if (runningRef.current && !hoveredRef.current && previousTime) {
          const elapsed = Math.min(time - previousTime, 50);
          rotation = (rotation + elapsed * 1.1025 / 90000) % 1;
          orbit = (orbit + elapsed * Math.PI * 2 / 24000) % (Math.PI * 2);
        }
        // Project a tilted orbit; the rear half passes behind the globe.
        const x = 61 * Math.cos(orbit);
        const y = 23 * Math.sin(orbit);
        const satellite = satelliteRef.current;
        if (satellite) {
          satellite.style.left = `${50 + x * 0.866 + y * 0.5}%`;
          satellite.style.top = `${50 - x * 0.5 + y * 0.866}%`;
          satellite.style.zIndex = Math.sin(orbit) < 0 ? '-1' : '2';
        }
        const size = Math.min(1200, Math.round(canvas.clientWidth * Math.min(window.devicePixelRatio || 1, 1.5)));
        const resized = canvas.width !== size || canvas.height !== size;
        if (resized) {
          canvas.width = canvas.height = size;
          gl.viewport(0, 0, size, size);
        }
        if (resized || lastDrawnRotation !== rotation) {
          gl.clear(gl.COLOR_BUFFER_BIT);
          gl.uniform1f(angle, rotation);
          gl.drawArrays(gl.TRIANGLES, 0, 6);
          lastDrawnRotation = rotation;
        }
      }
      previousTime = time;
      frame = requestAnimationFrame(draw);
    };
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; });
    observer.observe(canvas);
    // Listen on the hero because its decorative shade sits above the globe.
    // A circular hit test keeps the text and links fully interactive.
    const hero = canvas.closest('.earth-hero');
    const onPointerMove = event => {
      const bounds = canvas.getBoundingClientRect();
      if (event.pointerType === 'touch' || !bounds.width || !bounds.height) {
        hoveredRef.current = false;
        return;
      }
      const x = (event.clientX - bounds.left - bounds.width / 2) / (bounds.width / 2);
      const y = (event.clientY - bounds.top - bounds.height / 2) / (bounds.height / 2);
      hoveredRef.current = x * x + y * y <= 1 / (1.08 * 1.08);
    };
    const onPointerLeave = () => { hoveredRef.current = false; };
    hero?.addEventListener('pointermove', onPointerMove, { passive: true });
    hero?.addEventListener('pointerleave', onPointerLeave);
    hero?.addEventListener('pointercancel', onPointerLeave);
    const onContextLost = event => { event.preventDefault(); setReady(false); cancelAnimationFrame(frame); };
    canvas.addEventListener('webglcontextlost', onContextLost);
    image.onload = () => {
      if (disposed) return;
      // Resize to a power of two for older WebGL devices and a smaller GPU footprint.
      const textureCanvas = document.createElement('canvas');
      textureCanvas.width = 2048;
      textureCanvas.height = 1024;
      const context = textureCanvas.getContext('2d');
      if (!context) return;
      context.drawImage(image, 0, 0, 2048, 1024);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, textureCanvas);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform1i(gl.getUniformLocation(program, 'earth'), 0);
      setReady(true);
      frame = requestAnimationFrame(draw);
    };
    image.src = '/images/earth-daymap.jpg';
    return () => {
      disposed = true;
      image.onload = null;
      cancelAnimationFrame(frame);
      observer.disconnect();
      hero?.removeEventListener('pointermove', onPointerMove);
      hero?.removeEventListener('pointerleave', onPointerLeave);
      hero?.removeEventListener('pointercancel', onPointerLeave);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      resources.reverse().forEach(release => release());
    };
  }, []);

  return <>
    <div className={`earth-globe ${ready ? 'is-ready' : ''}`}>
      <svg className="earth-orbit" viewBox="0 0 100 100" aria-hidden="true">
        <ellipse cx="50" cy="50" rx="61" ry="23" transform="rotate(-30 50 50)" />
      </svg>
      <img src="/images/earth-eastern-hemisphere.jpg" alt="Earth viewed from space" aria-hidden={ready} width="1600" height="900" fetchpriority="high" className="earth-fallback" />
      <canvas ref={canvasRef} role="img" aria-hidden={!ready} aria-label="Three-dimensional Earth visualization using NASA Blue Marble imagery" />
      <svg ref={satelliteRef} className="earth-satellite" viewBox="0 0 64 40" aria-hidden="true">
        <g transform="rotate(-15 32 20)">
          <path className="satellite-panels" d="M2 13h19v14H2z M43 13h19v14H43z" />
          <path className="satellite-cells" d="M8 13v14m7-14v14M2 20h19m28-7v14m7-14v14M43 20h19" />
          <path className="satellite-body" d="M26 11h12v19H26z M21 18h5v4h-5z M38 18h5v4h-5z" />
          <path className="satellite-dish" d="M27 8q5-10 10 0z M32 8v3" />
          <path className="satellite-antenna" d="M32 30v7m-3 0h6" />
        </g>
      </svg>
    </div>
  </>;
}
