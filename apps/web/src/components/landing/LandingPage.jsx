import ExploreGuide, { FieldGuide } from './ExploreGuide.jsx';
import RotatingEarth from './RotatingEarth.jsx';
import { useMissionStore } from '@/store/useMissionStore.js';

const TEAM = [
  ['Pravin Tawade', 'Team lead · Mission architecture'],
  ['Kaushik Zade', 'Backend · Data connectors'],
  ['Sharv Dalal', 'Interface · Map experience'],
  ['Himanshu Sharma', 'NISAR data · Validation'],
  ['Sakshi Manav Tayade', 'Water regimes · Regional context'],
  ['Prashan Arya', 'Evidence cards · Quality assurance'],
];

function Arrow() { return <span className="arrow-disc" aria-hidden="true">↗</span>; }

export default function LandingPage() {
  return <>
    <section className="earth-hero" aria-labelledby="hero-title">
      <RotatingEarth />
      <div className="hero-shade" />
      <div className="page-container hero-content">
        <span className="section-kicker">OUR HOME PLANET / A NEW PERSPECTIVE</span>
        <h1 id="hero-title">Our changing Earth.<br />In clearer view.</h1>
        <p>Follow the monsoon. See water beyond the clouds. Discover what satellite radar can tell us about the places we call home.</p>
        <a href="#/explore" onClick={() => useMissionStore.getState().setAudienceMode('simple')} className="btn">Explore the water story <Arrow /></a>
        <a href="#about-sar" className="hero-secondary">Discover the science <span aria-hidden="true">↗</span></a>
      </div>
      <div className="page-container hero-topics">
        <a href="#start"><span className="section-kicker">FOR THE CURIOUS</span><strong>Start with the big picture <Arrow /></strong></a>
        <a href="#start"><span className="section-kicker">FOR RESEARCHERS</span><strong>Go deeper into the data <Arrow /></strong></a>
        <a href="#radar"><span className="section-kicker">THROUGH THE RADAR LENS</span><strong>See a landscape change <Arrow /></strong></a>
      </div>
      <a className="hero-credit" href="https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/" target="_blank" rel="noreferrer">EARTH VISUALIZATION · NASA BLUE MARBLE · NOT A LIVE SAR OBSERVATION ↗</a>
    </section>

    <section className="page-container featured-section" aria-labelledby="featured-title">
      <div className="editorial-heading"><div><span className="section-kicker">DISCOVER GEOSAR DRISHTI</span><h2 id="featured-title">A planet of possibilities.</h2></div><a href="#start" className="editorial-link">Find your starting point <Arrow /></a></div>
      <div className="feature-grid">
        <a href="#about-sar" className="feature-story feature-story-main"><img src="/images/earth-eastern-hemisphere.jpg" alt="" loading="lazy" width="1600" height="900" /><div><span className="section-kicker">EARTH SCIENCE / NISAR</span><h3>Clouds hide the view.<br />Radar tells another story.</h3><p>Discover how microwave echoes reveal water during the monsoon.</p><Arrow /></div></a>
        <a href="#start" className="feature-story"><img src="/preview/backscatter_before.png" alt="" loading="lazy" /><div><span className="section-kicker">TWO STUDY AREAS</span><h3>From Assam’s floodplains to Nagpur’s river basins.</h3><Arrow /></div></a>
        <a href="#field-guide" className="feature-story"><img src="/preview/new_water.png" alt="" loading="lazy" /><div><span className="section-kicker">SCIENCE FOR EVERYONE</span><h3>A clearer map starts with a little understanding.</h3><Arrow /></div></a>
      </div>
    </section>

    <ExploreGuide />

    <section id="radar" className="radar-section" aria-labelledby="radar-title">
      <div className="page-container">
        <div className="editorial-heading"><div><span className="section-kicker">OBSERVING CHANGE / NISAR · GANDAK RIVER · SEPT 2026</span><h2 id="radar-title">The story between two images.</h2></div><a href="#start" className="editorial-link">Explore current study areas <Arrow /></a></div>
        <p className="section-intro">Radar measures echoes from the ground. Calm open water looks dark; water trapped under vegetation bounces the signal back brighter. Compare two NISAR visits to see how the water-like signal shifts across the monsoon.</p>
        <div className="radar-grid">{[
          ['01 / BEFORE', '/preview/backscatter_before.png', '4 Sept 2026', 'An earlier NISAR L-band radar visit over the Gandak.'],
          ['02 / AFTER', '/preview/backscatter_after.png', '28 Sept 2026', 'A later visit during the monsoon, one day from the NASA MODIS view.'],
          ['03 / THE CHANGE', '/preview/new_water.png', 'Where the water signal shifted', 'Cyan marks newly open water; orange marks new water under vegetation that L-band reveals.'],
        ].map(([tag, image, title, description]) => <figure key={tag}><div className="radar-image"><img src={image} alt={description} loading="lazy" /><span className="section-kicker">{tag}</span></div><figcaption><h3>{title}</h3><p>{description}</p></figcaption></figure>)}</div>
        <p className="data-caption">NASA–ISRO NISAR L2 GCOV (γ⁰ HH), track 149 descending, Gandak River (Bihar–Nepal), 4 &amp; 28 Sept 2026 — composited from frames 074/075/076 and processed by this project. A radar-derived surface/canopy-water indication for inspection, not a confirmed flood: between these visits open water receded while water under vegetation spread.</p>
      </div>
    </section>

    <section id="about-sar" className="science-feature" aria-labelledby="science-title">
      <div className="page-container science-layout">
        <div><span className="section-kicker">THE SCIENCE / NASA–ISRO NISAR</span><h2 id="science-title">A closer look.<br />Beyond the visible.</h2><p>Rain clouds and darkness make it difficult to follow water with ordinary satellite photos. Synthetic Aperture Radar sends its own microwave pulses and listens for the echoes.</p><p>NISAR’s L-band observations help us study both open water and water indications beneath vegetation, visit by visit.</p><a href="#field-guide" className="editorial-link">Get to know radar <Arrow /></a></div>
        <div className="science-facts"><article><span className="section-kicker">01 / WATER</span><h3>More than what meets the eye.</h3><p>Explore open water and flooded-vegetation indications as separate map layers.</p></article><article><span className="section-kicker">02 / TIME</span><h3>A season, one visit at a time.</h3><p>See how many valid observations indicated water. Observation counts describe satellite visits, not days flooded.</p></article><article><span className="section-kicker">03 / EVIDENCE</span><h3>Every indication has a source.</h3><p>Inspect acquisition details, processing methods and limitations. Live, cached, offline and synthetic data states stay visible.</p></article></div>
      </div>
    </section>

    <FieldGuide />

    <section id="team" className="team-section page-container" aria-labelledby="team-title">
      <div className="editorial-heading"><div><span className="section-kicker">THE PEOPLE BEHIND THE PERSPECTIVE</span><h2 id="team-title">Curiosity brings us together.</h2></div><span className="team-event">InfoVerse Cosmos<br />NASA Space Apps 2026</span></div>
      <div className="team-layout"><img src="/team/infoverse-cosmos.png" alt="InfoVerse Cosmos — Orbiting Tomorrow" loading="lazy" /><div className="team-roster">{TEAM.map(([name, role]) => <article key={name}><span className="member-initials" aria-hidden="true">{name.split(' ').map(part => part[0]).join('').slice(0, 2)}</span><div><h3>{name}</h3><p>{role}</p></div></article>)}</div></div>
    </section>

    <section className="closing-feature"><div className="page-container"><span className="section-kicker">YOUR NEXT DISCOVERY</span><h2>There’s a whole<br />water story to explore.</h2><p>Choose a study area. Follow the observations. Find your own perspective.</p><a href="#start" className="btn">Start exploring <Arrow /></a></div></section>
  </>;
}
