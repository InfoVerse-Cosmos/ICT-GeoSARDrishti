// @vitest-environment jsdom
// API client: timeout, retry, envelope-safe fallback (SRS §7.2 rule 3).
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, loadFallbackManifest } from "@/api/client.js";

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("api client", () => {
  it("defaults to localhost:8000 when VITE_API_BASE_URL is unset", () => {
    expect(api.base).toBe(import.meta.env.VITE_API_BASE_URL || "http://localhost:8000");
  });

  it("returns the backend envelope on success", async () => {
    const env = { status: "ok", data: { x: 1 }, fallback_active: false };
    const fetch = vi.fn(() => ok(env));
    vi.stubGlobal("fetch", fetch);
    expect(await api.health()).toEqual(env);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe(`${api.base}/api/v1/health`);
  });

  it("retries once on HTTP error then returns a safe CLIENT_FALLBACK envelope", async () => {
    const fetch = vi.fn(() => Promise.resolve({ ok: false, status: 503, json: () => ({}) }));
    vi.stubGlobal("fetch", fetch);
    const res = await api.listAois();
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(res.status).toBe("unavailable");
    expect(res.source_mode).toBe("CLIENT_FALLBACK");
    expect(res.fallback_active).toBe(true);
    expect(res.data).toBeNull();
    expect(res.warning).toContain("HTTP 503");
  });

  it("recovers if the retry succeeds (cold-start backend)", async () => {
    const fetch = vi
      .fn()
      .mockImplementationOnce(() => Promise.reject(new Error("ECONNREFUSED")))
      .mockImplementationOnce(() => ok({ status: "ok", data: {} }));
    vi.stubGlobal("fetch", fetch);
    expect((await api.health()).status).toBe("ok");
  });

  it("aborts a hung request after the timeout and falls back", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn(
      (_url, { signal }) =>
        new Promise((_, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")))),
    );
    vi.stubGlobal("fetch", fetch);
    const p = api.health();
    await vi.advanceTimersByTimeAsync(6000 + 800 + 6000 + 10);
    const res = await p;
    expect(res.status).toBe("unavailable");
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("builds overlay PNG URLs with and without date", () => {
    expect(api.layerPngUrl("aoi_assam_majuli", "open_water")).toBe(
      `${api.base}/api/v1/layers/aoi_assam_majuli/open_water.png`,
    );
    expect(api.layerPngUrl("aoi_assam_majuli", "open_water", "2026-07-22")).toBe(
      `${api.base}/api/v1/layers/aoi_assam_majuli/open_water.png?date=2026-07-22`,
    );
  });

  it("encodes the bbox for the live Earthdata query", async () => {
    const fetch = vi.fn(() => ok({ status: "ok" }));
    vi.stubGlobal("fetch", fetch);
    await api.earthdataLive("93.9,26.75,94.3,27.05");
    expect(fetch.mock.calls[0][0]).toContain("bbox=93.9%2C26.75%2C94.3%2C27.05");
  });

  it("sends inspect lat/lon as query params", async () => {
    const fetch = vi.fn(() => ok({ status: "ok" }));
    vi.stubGlobal("fetch", fetch);
    await api.inspect("aoi_assam_majuli", 26.9421, 94.1834);
    expect(fetch.mock.calls[0][0]).toBe(
      `${api.base}/api/v1/aois/aoi_assam_majuli/inspect?lat=26.9421&lon=94.1834`,
    );
  });

  it("POSTs evidence-card telemetry as JSON", async () => {
    const fetch = vi.fn(() => ok({ status: "ok" }));
    vi.stubGlobal("fetch", fetch);
    const payload = { aoi_id: "aoi_assam_majuli", telemetry: { hydroperiod: { m: 6, n: 9 } } };
    await api.evidenceCard(payload);
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual(payload);
  });
});

describe("offline mirror", () => {
  it("loads the bundled fallback manifest", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({ aois: [{ aoi_id: "aoi_assam_majuli" }] })));
    expect((await loadFallbackManifest()).aois[0].aoi_id).toBe("aoi_assam_majuli");
  });

  it("returns null instead of throwing when the mirror is missing", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    expect(await loadFallbackManifest()).toBeNull();
  });
});
