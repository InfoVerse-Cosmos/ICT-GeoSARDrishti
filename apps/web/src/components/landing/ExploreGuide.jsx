import { useState } from 'react';
import { useMissionStore } from '@/store/useMissionStore.js';

const VIEWS = {
  simple: { title: 'Understand the water story.', description: 'Start with a satellite map and clear explanations. No radar experience needed.', steps: [['Find water', 'See where radar indicates open water or water beneath vegetation.'], ['Follow the season', 'Move between observation dates to understand how the landscape changes.'], ['Know what to check', 'Read plain-language summaries and places that may need a field visit.']], action: 'Explore in simple mode' },
  scientific: { title: 'Follow the signal to the evidence.', description: 'Inspect radar measurements and the assumptions behind each indication.', steps: [['Inspect acquisitions', 'Review polarization, product maturity and source provenance.'], ['Compare measurements', 'Explore pixel trajectories, water layers and wet-observation persistence.'], ['Assess the result', 'Review reference agreement, evidence cards and inspection candidates.']], action: 'Open scientific workspace' },
};

export default function ExploreGuide() {
  const [mode, setMode] = useState('simple');
  const [area, setArea] = useState('aoi_assam_majuli');
  const view = VIEWS[mode];
  const launch = () => {
    useMissionStore.getState().setAudienceMode(mode);
    useMissionStore.getState().setActiveAoi(area);
  };
  return <section id="start" className="mission-guide mx-auto max-w-[1500px] px-4 py-14 sm:px-6" aria-labelledby="guide-title">
    <div className="section-kicker">01 / YOUR MISSION STARTS HERE</div>
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div><h2 id="guide-title" className="text-3xl font-bold tracking-tight md:text-4xl">One Earth. Two ways to explore.</h2><p className="mt-3 text-muted">Choose your level of detail. Switch anytime inside the map.</p></div>
      <div className="audience-switch" role="group" aria-label="Choose your experience">
        <button aria-pressed={mode === 'simple'} onClick={() => setMode('simple')}>Everyone</button>
        <button aria-pressed={mode === 'scientific'} onClick={() => setMode('scientific')}>Researchers &amp; analysts</button>
      </div>
    </div>
    <div className="guide-console">
      <div className="guide-copy"><span className="section-kicker">{mode === 'simple' ? 'EXPLORER / SIMPLE MODE' : 'ANALYST / SCIENTIFIC MODE'}</span><h3 className="mt-3 text-2xl font-semibold">{view.title}</h3><p className="mt-3 text-muted">{view.description}</p>
        <label htmlFor="landing-area" className="mb-2 mt-7 block text-sm font-semibold">Choose a study area</label>
        <select id="landing-area" value={area} onChange={event => setArea(event.target.value)}><option value="aoi_assam_majuli">Majuli–Kaziranga · Assam</option><option value="aoi_nagpur_kanhan">Kanhan–Pench · Nagpur</option></select>
        <a href="#/explore" onClick={launch} className="btn mt-4">{view.action} <span aria-hidden="true">↗</span></a>
      </div>
      <ol className="guide-steps" aria-label={`${mode} mode features`}>{view.steps.map(([title, description], index) => <li key={title}><span className="step-number">0{index + 1}</span><div><h4 className="font-semibold">{title}</h4><p className="mt-1 text-sm leading-relaxed text-muted">{description}</p></div></li>)}</ol>
    </div>
    <div className="reading-key"><strong>Reading the map</strong><span><i style={{ background: '#0284c7' }} />Open water</span><span><i style={{ background: '#10b981' }} />Water beneath vegetation</span><span><i style={{ background: '#f59e0b' }} />Wet-observation frequency</span><a href="#field-guide">What do these mean? ↓</a></div>
  </section>;
}

export function FieldGuide() {
  return <section id="field-guide" className="mx-auto max-w-[1500px] px-4 py-14 sm:px-6" aria-labelledby="field-guide-title">
    <div className="section-kicker">FIELD GUIDE / THE ESSENTIALS</div><h2 id="field-guide-title" className="text-3xl font-bold tracking-tight">A little context. A clearer picture.</h2><p className="mb-7 mt-3 text-muted">Open a question for a plain-language explanation.</p>
    <div className="field-questions">{[
      ['What am I looking at?', 'A satellite map with radar-derived water indications. Blue marks open water; green marks indications of water beneath vegetation. Use the layer controls to explore one type at a time.'],
      ['What does “wet in M of N observations” mean?', 'If a location is wet in 6 of 9 valid observations, radar detected a water indication on six satellite visits. This does not mean six days of flooding: satellites do not observe every day.'],
      ['What is SAR, and why use it during the monsoon?', 'Synthetic Aperture Radar (SAR) sends microwave pulses toward Earth and measures their echoes. It can observe through clouds and at night, helping us study water during the monsoon.'],
      ['Does a highlighted area confirm flooding or damage?', 'A highlighted area is an indication to investigate. Radar response also depends on vegetation, terrain and acquisition conditions. It does not measure flood depth or confirm damage.'],
      ['Where did the data come from?', 'Open Provenance in the workspace to inspect sources and processing details. Connection labels distinguish live API, local cache and offline mirror states; synthetic test data carries a visible warning.'],
      ['Can I change the level of detail later?', 'Yes. Use Simple or Scientific in the workspace header. Simple prioritizes explanations; Scientific adds acquisition details, measurements and evidence panels.'],
    ].map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
  </section>;
}
