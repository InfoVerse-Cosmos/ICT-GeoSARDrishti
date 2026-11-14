// @vitest-environment jsdom
// Mission store + Top bar + Monsoon time slider (SRS §3.2, §4.1, §4.2).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LAYERS, useMissionStore } from "@/store/useMissionStore.js";
import MonsoonTimeSlider from "@/components/MonsoonTimeSlider.jsx";
import TopTelemetryBar from "@/components/TopTelemetryBar.jsx";
import ExposureTable from "@/components/ExposureTable.jsx";
import EvidenceCardPanel from "@/components/EvidenceCardPanel.jsx";
import fallbackManifest from "../../public/fallback_data/manifest.json";

const INITIAL = useMissionStore.getState();
const TIMELINE = [
  { date: "2026-07-22", maturity: "PROVISIONAL", granule_id: "G_0722", track_frame: "T12/F34", polarization: "HH+HV" },
  { date: "2026-08-15", maturity: "PROVISIONAL" },
  { date: "2026-11-07", maturity: "VALIDATED", granule_id: "G_1107", track_frame: "T12/F34", polarization: "HH+HV" },
];
const AOIS = [{ aoi_id: "aoi_assam_majuli" }, { aoi_id: "aoi_nagpur_kanhan" }];

beforeEach(() => useMissionStore.setState(INITIAL, true));
afterEach(cleanup);

// ------------------------------------------------------------ store
describe("mission store", () => {
  it("defaults to the Assam primary AOI", () => {
    expect(useMissionStore.getState().activeAoiId).toBe("aoi_assam_majuli");
    expect(useMissionStore.getState().connection).toBe("CONNECTING");
  });

  it("setTimeline selects the latest acquisition", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    expect(useMissionStore.getState().activeDate).toBe("2026-11-07");
  });

  it("setTimeline with no acquisitions clears the date", () => {
    useMissionStore.getState().setTimeline([]);
    expect(useMissionStore.getState().activeDate).toBeNull();
  });

  it("switching AOI clears the clicked pixel and evidence card", () => {
    const s = useMissionStore.getState();
    s.setClickedPixel({ lat: 1, lon: 2 });
    s.setEvidenceCard({ confidence: "Low" });
    s.setActiveAoi("aoi_nagpur_kanhan");
    const after = useMissionStore.getState();
    expect(after.activeAoiId).toBe("aoi_nagpur_kanhan");
    expect(after.clickedPixel).toBeNull();
    expect(after.evidenceCard).toBeNull();
  });

  it("layer palette matches the SRS colour-blind-safe palette", () => {
    const colours = Object.fromEntries(LAYERS.map((l) => [l.id, l.color.toUpperCase()]));
    expect(colours.open_water).toBe("#0284C7");
    expect(colours.flooded_veg).toBe("#10B981");
  });
});

// ------------------------------------------------------------ time slider
describe("MonsoonTimeSlider", () => {
  it("always shows the 27 Jul – 10 Aug acquisition gap band", () => {
    render(<MonsoonTimeSlider />);
    expect(screen.getByText("SENSOR ACQUISITION GAP (27 JUL – 10 AUG)")).toBeTruthy();
  });

  it("shows an empty state with no acquisitions", () => {
    render(<MonsoonTimeSlider />);
    expect(screen.getByText("No acquisitions loaded.")).toBeTruthy();
  });

  it("renders one tick per acquisition with maturity in the tooltip", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    render(<MonsoonTimeSlider />);
    expect(screen.getAllByTitle(/^2026-\d\d-\d\d · /)).toHaveLength(3);
    expect(screen.getByTitle("2026-11-07 · VALIDATED")).toBeTruthy();
    expect(screen.getByTitle("2026-07-22 · PROVISIONAL")).toBeTruthy();
  });

  it("clicking a tick sets the active date", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    render(<MonsoonTimeSlider />);
    fireEvent.click(screen.getByText("07-22"));
    expect(useMissionStore.getState().activeDate).toBe("2026-07-22");
  });

  it("VALIDATED dates use the cyan badge, PROVISIONAL the ISRO orange badge", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    render(<MonsoonTimeSlider />);
    const dot = (title) => screen.getByTitle(title).querySelector("span");
    expect(dot("2026-11-07 · VALIDATED").className).toContain("bg-cyan");
    expect(dot("2026-07-22 · PROVISIONAL").className).toContain("bg-isro");
  });

  it("a date that falls inside the gap is hatched", () => {
    useMissionStore.getState().setTimeline([{ date: "2026-08-01", maturity: "PROVISIONAL" }]);
    render(<MonsoonTimeSlider />);
    expect(screen.getByTitle("2026-08-01 · PROVISIONAL").className).toContain("acq-gap");
  });
});

// ------------------------------------------------------------ top bar
describe("TopTelemetryBar", () => {
  // The full telemetry pills + Provenance button belong to Scientist mode.
  beforeEach(() => useMissionStore.setState({ audienceMode: "scientist" }));

  it("offers both AOIs with human-readable names", () => {
    useMissionStore.getState().setAois(AOIS);
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByRole("option", { name: "Majuli–Kaziranga [Assam]" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Kanhan–Pench [Nagpur]" })).toBeTruthy();
  });

  it("changing the selector switches the active AOI", () => {
    useMissionStore.getState().setAois(AOIS);
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "aoi_nagpur_kanhan" } });
    expect(useMissionStore.getState().activeAoiId).toBe("aoi_nagpur_kanhan");
  });

  it("shows granule, track/frame, polarization and maturity for the active date", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText("GRANULE G_1107")).toBeTruthy();
    expect(screen.getByText("T/F T12/F34")).toBeTruthy();
    expect(screen.getByText("HH+HV")).toBeTruthy();
    expect(screen.queryByText("SYNTHETIC TEST DATA")).toBeNull();
    expect(screen.getByText("VALIDATED")).toBeTruthy();
  });

  it("maturity badge follows the selected date", () => {
    useMissionStore.getState().setTimeline(TIMELINE);
    useMissionStore.getState().setActiveDate("2026-07-22");
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText("PROVISIONAL")).toBeTruthy();
    expect(screen.getByText("GRANULE G_0722")).toBeTruthy();
  });

  it.each([
    ["LIVE_API", "LIVE API"],
    ["LOCAL_CACHE", "LOCAL CACHE"],
    ["OFFLINE", "OFFLINE MIRROR"],
    ["CONNECTING", "ESTABLISHING UPLINK…"],
  ])("connection %s renders %s", (connection, label) => {
    useMissionStore.setState({ connection });
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("flags fallback mode on the connection pill", () => {
    useMissionStore.setState({ connection: "LIVE_API", fallbackActive: true });
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText("LIVE API · FALLBACK")).toBeTruthy();
  });

  it("Provenance button calls the handler", () => {
    let opened = false;
    render(<TopTelemetryBar onOpenProvenance={() => (opened = true)} />);
    fireEvent.click(screen.getByText("Provenance"));
    expect(opened).toBe(true);
  });
});

// ------------------------------------------------------------ dual-audience
describe("audience mode (Simple default)", () => {
  it("defaults to Simple and hides the scientist pills + Provenance button", () => {
    expect(useMissionStore.getState().audienceMode).toBe("simple");
    useMissionStore.getState().setTimeline(TIMELINE);
    render(<TopTelemetryBar onOpenProvenance={() => {}} onOpenReport={() => {}} />);
    expect(screen.queryByText("GRANULE G_1107")).toBeNull();
    expect(screen.queryByText("Provenance")).toBeNull();
  });

  it("Report button calls the handler in Simple mode", () => {
    let opened = false;
    render(<TopTelemetryBar onOpenProvenance={() => {}} onOpenReport={() => (opened = true)} />);
    fireEvent.click(screen.getByText("📊 Report"));
    expect(opened).toBe(true);
  });

  it("switching to Scientist swaps the satellite basemap back to dark", () => {
    useMissionStore.getState().setAudienceMode("simple");
    expect(useMissionStore.getState().basemap).toBe("satellite");
    useMissionStore.getState().setAudienceMode("scientist");
    expect(useMissionStore.getState().basemap).toBe("dark");
  });
});

// ------------------------------------------------------------ offline mirror content
describe("bundled offline mirror (public/fallback_data/manifest.json)", () => {
  it("contains both AOIs with valid bounds", () => {
    const ids = fallbackManifest.aois.map((a) => a.aoi_id);
    expect(ids).toEqual(expect.arrayContaining(["aoi_assam_majuli", "aoi_nagpur_kanhan"]));
    for (const a of fallbackManifest.aois) {
      const [w, s, e, n] = a.bounds;
      expect(w).toBeLessThan(e);
      expect(s).toBeLessThan(n);
    }
  });
});

// ------------------------------------------------------------ new features
describe("time slider playback", () => {
  it("PLAY advances to the next acquisition and wraps around", async () => {
    vi.useFakeTimers();
    useMissionStore.getState().setTimeline(TIMELINE);
    useMissionStore.getState().setActiveDate("2026-07-22");
    render(<MonsoonTimeSlider />);
    fireEvent.click(screen.getByLabelText("Play monsoon animation"));
    await act(async () => vi.advanceTimersByTime(1400));
    expect(useMissionStore.getState().activeDate).toBe("2026-08-15");
    await act(async () => vi.advanceTimersByTime(2800));
    expect(useMissionStore.getState().activeDate).toBe("2026-07-22");
    vi.useRealTimers();
  });

  it("PLAY is disabled with fewer than two acquisitions", () => {
    useMissionStore.getState().setTimeline([TIMELINE[0]]);
    render(<MonsoonTimeSlider />);
    expect(screen.getByLabelText("Play monsoon animation").disabled).toBe(true);
  });
});

describe("top bar honesty badges", () => {
  beforeEach(() => useMissionStore.setState({ audienceMode: "scientist" }));

  it("shows the fallback plan, single-pol mode and synthetic-data warning", () => {
    useMissionStore.getState().setTimeline([{ date: "2026-10-09", maturity: "PROVISIONAL", polarization: "HH" }],
      { fallback_plan: "C", single_pol_mode: true, synthetic_test_data: true });
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText("PLAN C")).toBeTruthy();
    expect(screen.getByText("SINGLE-POL HH")).toBeTruthy();
    expect(screen.getByText("SYNTHETIC TEST DATA")).toBeTruthy();
  });

  it("shortens a real ~100-char NISAR granule id", () => {
    useMissionStore.getState().setTimeline([{ date: "2026-11-02", maturity: "VALIDATED",
      granule_id: "NISAR_L2_PR_GCOV_034_135_D_076_2005_DHDH_M_20261102T134916_20261102T134950_P05036_N_F_J_001" }]);
    render(<TopTelemetryBar onOpenProvenance={() => {}} />);
    expect(screen.getByText("GRANULE 034_135_D_076 · 20261102")).toBeTruthy();
  });
});

describe("Inspection log", () => {
  const exposure = { note: "Inspection candidates only — never a damage claim.", ranked: [
    { id: "a", name: "NH715K", kind: "road", wet_observations: 2, total_observations: 2, center: [94.1, 26.9] },
    { id: "b", name: "Kamalabari", kind: "village", wet_observations: 1, total_observations: 2, center: [94.0, 26.95] },
  ] };

  it("lists candidates ranked by wet observations and flies the map on click", () => {
    useMissionStore.setState({ exposure });
    render(<ExposureTable />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].textContent).toContain("NH715K");
    fireEvent.click(screen.getByText("Kamalabari"));
    expect(useMissionStore.getState().flyTo.center).toEqual([94.0, 26.95]);
  });

  it("filters by kind and re-sorts by name", () => {
    useMissionStore.setState({ exposure });
    render(<ExposureTable />);
    fireEvent.change(screen.getByLabelText("Filter by kind"), { target: { value: "village" } });
    expect(screen.getAllByRole("row")).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("Filter by kind"), { target: { value: "all" } });
    fireEvent.click(screen.getByText(/^Name/));
    expect(screen.getAllByRole("row")[1].textContent).toContain("Kamalabari");
  });

  it("shows the empty-state note when no pack exists", () => {
    useMissionStore.setState({ exposure: { ranked: [], warning: "No exposure pack found yet." } });
    render(<ExposureTable />);
    expect(screen.getByText("No exposure pack found yet.")).toBeTruthy();
  });
});

describe("Evidence card panel", () => {
  it("shows the outside-AOI message", () => {
    useMissionStore.setState({ clickedPixel: { status: "outside_aoi", warning: "Clicked coordinate lies outside" } });
    render(<EvidenceCardPanel />);
    expect(screen.getByText("Clicked coordinate lies outside")).toBeTruthy();
  });

  it("renders every card field plus the verbatim caveat", () => {
    useMissionStore.setState({
      clickedPixel: { status: "ok", lat: 26.9, lon: 94.1 },
      evidenceCard: { mode: "deterministic", location: "26.9, 94.1", hydrological_regime: "Seasonally Flooded Canopy / Tall Grassland",
        monsoon_persistence: "Wet in 6 of 9 valid NISAR L-band observations (66.7%).", radar_physics_evidence: "+4.6 dB",
        land_cover_context: "Herbaceous Wetland", confidence: "Moderate-High",
        caveat: "This is a radar-derived surface/canopy-water indication for field inspection, not a confirmed flood-depth measurement.",
        data_notice: "SYNTHETIC TEST DATA — not a NISAR observation." },
    });
    render(<EvidenceCardPanel />);
    expect(screen.getByText("Wet in 6 of 9 valid NISAR L-band observations (66.7%).")).toBeTruthy();
    expect(screen.getByText("Moderate-High")).toBeTruthy();
    expect(screen.getByText(/not a confirmed flood-depth measurement/)).toBeTruthy();
    expect(screen.getByText("SYNTHETIC TEST DATA — not a NISAR observation.")).toBeTruthy();
  });
});
