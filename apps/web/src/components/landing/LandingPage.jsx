import { useRef } from 'react';
import RotatingEarth from './RotatingEarth.jsx';
import { useMissionStore } from '@/store/useMissionStore.js';

const TEAM = [
  ['Pravin Tawade', 'Team lead · Mission architecture'],
  ['Himanshu Sharma', 'NISAR data · Validation'],
  ['Sharv Dalal', 'Interface · Map experience'],
  ['Sakshi Manav Tayade', 'Water regimes · Regional context'],
  ['Prashan Arya', 'Evidence cards · Quality assurance'],
  ['Kaushik Zade', 'Backend · Data connectors'],
];

function Arrow() { return <span className="arrow-disc" aria-hidden="true">↗</span>; }

export default function LandingPage() {
  const videoDialog = useRef(null);
  const videoTrigger = useRef(null);
  const video = <iframe src="https://www.youtube-nocookie.com/embed/mqZ5vd-t40s" title="GeoSAR Drishti project walkthrough" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowFullScreen />;
  return <>
    <section className="earth-hero" aria-labelledby="hero-title">
      <RotatingEarth />
      <div className="hero-shade" />
      <div className="page-container hero-content">
        <span className="section-kicker">OUR HOME PLANET / A NEW PERSPECTIVE</span>
        <h1 id="hero-title">Our changing Earth.<br />In clearer view.</h1>
        <p>Follow the monsoon. See water beyond the clouds. Discover what satellite radar can tell us about the places we call home.</p>
        <a href="#/explore" onClick={() => useMissionStore.getState().setAudienceMode('simple')} className="btn">Start exploring <Arrow /></a>
        <a href="#about-sar" className="hero-secondary">Discover the science <span aria-hidden="true">↗</span></a>
      </div>
      <a className="hero-credit" href="https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/" target="_blank" rel="noreferrer">EARTH VISUALIZATION · NASA BLUE MARBLE · NOT A LIVE SAR OBSERVATION ↗</a>
    </section>


    <section id="about-sar" className="page-container story-section" aria-labelledby="challenge-title">
      <span className="section-kicker">01 / THE CHALLENGE &middot; DANCING WITH THE SARS</span>
      <div className="story-split"><h2 id="challenge-title">The problem: tracking water<br />through monsoon clouds.</h2><div><p className="story-lead">Clouds, darkness and dense vegetation can hide a changing landscape. Radar gives us another way to look.</p><p>Synthetic Aperture Radar (SAR) uses microwave echoes to observe Earth day and night, through cloud cover. The challenge is to turn complex radar data into clear, useful stories about changes on our planet.</p><p>Our focus: helping people explore open water, water indications beneath vegetation and changes across satellite visits using NASA–ISRO NISAR observations.</p><div className="resource-links"><a href="https://search.earthdata.nasa.gov/" target="_blank" rel="noreferrer">NASA Earthdata ↗</a><a href="https://search.asf.alaska.edu/" target="_blank" rel="noreferrer">ASF data search ↗</a></div></div></div>
    </section>

    <section id="solution" className="page-container story-section" aria-labelledby="solution-title"><span className="section-kicker">02 / OUR SOLUTION</span><div className="story-split"><h2 id="solution-title">Our solution: explainable<br />radar water intelligence.</h2><div><p className="story-lead">GeoSAR Drishti turns NISAR observations into maps, comparisons and evidence people can use.</p><p>Our interactive workspace separates open-water and possible water-under-vegetation signals, counts wet indications across valid visits, and explains individual pixels. Users can review roads and settlements that may need field inspection and share a report with the observation dates and limitations.</p></div></div><div className="solution-steps">{[
      ['01', 'See the water', 'Explore open water and water beneath vegetation as distinct radar-derived layers.'],
      ['02', 'Follow the change', 'Move through acquisitions and compare repeat water indications across valid observations.'],
      ['03', 'Inspect & share', 'Trace a signal to its evidence and bring the findings into a plain-language report.'],
    ].map(([n,title,description]) => <article key={n}><span className="section-kicker">{n}</span><h3>{title}</h3><p>{description}</p></article>)}</div></section>

    <section id="video" className="video-section" aria-labelledby="project-materials-title"><div className="page-container"><div className="editorial-heading"><div><span className="section-kicker">03 / PRESENTATION &amp; DEMO</span><h2 id="project-materials-title">Explore our project.</h2></div></div>
      <div className="project-media-grid">
        <article className="project-media-item"><a className="presentation-card media-preview" href="/preview/GeoSAR_Drishti_Judging_Presentation.pdf" target="_blank" rel="noopener noreferrer" aria-label="Open GeoSAR Drishti presentation preview in a new tab"><span className="presentation-format"><span className="file-badge">PDF</span> PROJECT PRESENTATION</span><div className="presentation-summary"><svg viewBox="0 0 64 64" aria-hidden="true"><rect x="8" y="8" width="48" height="36" rx="3" /><path d="M32 44v12M20 56h24M18 32l9-9 8 6 11-12" /></svg><strong>GeoSAR Drishti</strong><span>Radar water intelligence.<br />From the challenge to the evidence.</span></div><span className="presentation-download">Open slide deck <span aria-hidden="true">&#x2197;</span></span></a><div className="media-card-body"><span className="section-kicker">READ / PRESENTATION</span><h3>Project presentation</h3><p>Explore our approach, case study and findings in the judging slide deck.</p><a className="editorial-link" href="/preview/GeoSAR_Drishti_Judging_Presentation.pptx" download>Download PowerPoint</a></div></article>
        <article className="project-media-item"><div className="video-card media-preview">{video}</div><div className="media-card-body"><span className="section-kicker">WATCH / VIDEO DEMO</span><div className="media-card-heading"><h3>Project walkthrough</h3><button ref={videoTrigger} className="editorial-link video-maximize" onClick={() => videoDialog.current?.showModal()}>Maximize video <span aria-hidden="true">&#x2922;</span></button></div><p>See the workspace, compare water layers and inspect the radar evidence.</p></div></article>
      </div></div>
    <dialog ref={videoDialog} className="video-dialog" aria-label="Project walkthrough" onClick={event => { if (event.target === event.currentTarget) videoDialog.current.close(); }} onClose={() => videoTrigger.current?.focus()}><button className="video-close" onClick={() => videoDialog.current.close()} autoFocus>Close video &#x2715;</button><div className="video-card">{video}</div></dialog></section>

    <section id="radar" className="case-section" aria-labelledby="case-title"><div className="page-container">
      <span className="section-kicker">04 / THE NEED ON THE GROUND</span><h2 id="case-title">Flood case studies: Assam and Texas.</h2>
      <article className="assam-case"><div className="case-heading"><div><span className="section-kicker">OUR CASE STUDY / ASSAM, INDIA</span><h3>Assam floods 2026: the Brahmaputra Bend.</h3></div><p>Repeated flooding during Assam’s 2026 monsoon affected communities, farmland and infrastructure. Our Brahmaputra Bend demonstration compares three radar observations—10 July, 22 July and 7 November—to show water patterns, repeated wet indications and locations for field inspection. These are AOI-level indications; three observations do not establish continuous flood duration.</p></div>
      <div className="demo-gallery">{[
        [2, 'Open water', 'A satellite basemap puts radar-derived open-water indications in their landscape context.'],
        [3, 'Water beneath vegetation', 'A separate layer highlights water indications beneath trees and crops.'],
        [4, 'Repeatedly wet areas', 'Compare how often water was indicated across the available satellite visits.'],
        [1, 'Inspect the radar evidence', 'Explore pixel trajectories, acquisition details and the source of each indication.'],
        [6, 'Understand a location', 'Read a plain-language explanation alongside the selected point on the map.'],
        [5, 'Bring the evidence together', 'An analysis report summarizes observations, changes and candidates for field inspection.'],
      ].map(([number, title, description]) => <figure key={number}><a href={`/images/projectdemo${number}.jpeg`} target="_blank" rel="noreferrer" aria-label={`Enlarge ${title} screenshot`}><img src={`/images/projectdemo${number}.jpeg`} alt={`GeoSAR Drishti Brahmaputra Bend workspace: ${title.toLowerCase()}`} loading="lazy" width="1536" height="700" /><span className="image-expand" aria-hidden="true">&#x2197;</span></a><figcaption><h4>{title}</h4><p>{description}</p></figcaption></figure>)}</div>
      <p className="data-caption">Project screenshots supplied by the team. Radar-derived water indications support field inspection; they do not confirm flood depth or damage. Persistence counts valid satellite observations, not days flooded.</p></article>
      <article className="us-case"><figure><img src="/images/texas-floods.jpg" alt="NASA GPM visualization of the storm associated with the July 4, 2025 Texas floods" loading="lazy" /><figcaption>Storm visualization &middot; NASA Scientific Visualization Studio / GPM</figcaption></figure><div><span className="section-kicker">U.S. CONTEXT / TEXAS &middot; JULY 2025</span><h3>Texas floods 2025: satellite data for response.</h3><p>The July 4, 2025 Texas Hill Country floods show why accessible Earth observations matter. NASA supported response agencies with satellite and airborne data; its OPERA products helped map surface water.</p><p>This event motivates our vision for clearer water information. It is an external reference case, not an event analyzed by our Assam demonstration.</p><a className="editorial-link" href="https://science.data.nasa.gov/disasters/news-events-stories/texas-floods-july-2025" target="_blank" rel="noreferrer">Read NASA's case study <Arrow /></a></div></article>
    </div></section>

    <section id="applications" className="page-container story-section" aria-labelledby="applications-title"><span className="section-kicker">05 / APPLICATIONS &amp; VISION</span><h2 id="applications-title">Who can use GeoSAR Drishti?</h2><p className="section-intro applications-intro">Our vision: make radar-based water assessment accessible to researchers, NGOs and local teams, helping them choose where to investigate and verify conditions on the ground.</p><div className="application-grid">{[
      ['Research & education', 'Explore radar signatures, compare acquisitions and teach how satellite observations describe changing water.'],
      ['NGOs & communities', 'Use accessible maps and reports to guide local questions and plan field verification.'],
      ['Disaster management', 'Review water-change indications and identify locations that may need closer inspection.'],
      ['Agriculture & ecosystems', 'Study seasonal water patterns around crops, wetlands and floodplain habitats.'],
    ].map(([title,description]) => <article key={title}><h3>{title}</h3><p>{description}</p></article>)}</div></section>
    <section id="team" className="team-section page-container" aria-labelledby="team-title">
      <div className="editorial-heading"><div><span className="section-kicker">THE PEOPLE BEHIND THE PERSPECTIVE</span><h2 id="team-title">Curiosity brings us together.</h2></div><span className="team-event">InfoVerse Cosmos<br />NASA Space Apps 2026</span></div>
      <p className="section-intro">We are InfoVerse Cosmos, a multidisciplinary team bringing together radar science, regional knowledge and software engineering. For NASA Space Apps 2026, we are building GeoSAR Drishti to make satellite water observations easier to explore, question and share.</p><div className="team-layout"><img src="/team/infoverse-cosmos.png" alt="InfoVerse Cosmos — Orbiting Tomorrow" loading="lazy" /><div className="team-roster">{TEAM.map(([name, role]) => <article key={name}><span className="member-initials" aria-hidden="true">{name.split(' ').map(part => part[0]).join('').slice(0, 2)}</span><div><h3>{name}</h3><p>{role}</p></div></article>)}</div></div>
    </section>

  </>;
}
