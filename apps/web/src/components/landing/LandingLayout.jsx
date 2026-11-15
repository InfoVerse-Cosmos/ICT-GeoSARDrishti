import { useEffect, useRef, useState } from 'react';
import LandingPage from './LandingPage.jsx';
import { useMissionStore } from '@/store/useMissionStore.js';
import { ThemeToggle } from './ThemeToggle.jsx';
import '@/landing.css';

const NAV_LINKS = [
  ['The challenge', '#about-sar', 'Why radar matters for water observation'],
  ['Our solution', '#solution', 'From radar observations to readable evidence'],
  ['Presentation & demo', '#video', 'Download the slides and watch the walkthrough'],
  ['Radar in action', '#radar', 'Explore Assam and a U.S. reference case'],
  ['Applications', '#applications', 'Research, NGOs and our vision'],
  ['Our team', '#team', 'Meet InfoVerse Cosmos'],
];

export default function LandingLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);
  useEffect(() => {
    if (!menuOpen) return;
    const dismiss = event => {
      if (event.type === 'keydown' && event.key === 'Escape') {
        setMenuOpen(false);
        triggerRef.current?.focus();
      } else if (event.type === 'pointerdown' && !menuRef.current?.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', dismiss);
    return () => {
      document.removeEventListener('keydown', dismiss);
      document.removeEventListener('pointerdown', dismiss);
    };
  }, [menuOpen]);

  return <div className="landing light">
    <a href="#landing-content" className="landing-skip">Skip to content</a>
    <header className="agency-header">
      <nav className="agency-nav" aria-label="Main navigation">
        <div className="explore-navigation" ref={menuRef}>
          <button ref={triggerRef} className="explore-trigger" aria-expanded={menuOpen} aria-controls="explore-navigation" onClick={() => setMenuOpen(!menuOpen)}>Explore <span aria-hidden="true">{menuOpen ? '−' : '+'}</span></button>
          <span className="nav-project-label">EARTH / WATER / DISCOVERY</span>
          {menuOpen && <div className="explore-dropdown" id="explore-navigation">
            <span className="section-kicker">EXPLORE GEOSAR DRISHTI</span>
            {NAV_LINKS.map(([label, href, description]) => <a key={href} href={href} onClick={() => setMenuOpen(false)}><strong>{label} <span aria-hidden="true">↗</span></strong><small>{description}</small></a>)}
          </div>}
        </div>
        <a href="#/" className="agency-wordmark" aria-label="GeoSAR Drishti home"><img className="agency-logo" src="/images/GeoSAR.jpeg" alt="GeoSAR Drishti — Earth insights through radar vision" width="1600" height="800" /></a>
        <div className="agency-nav-actions"><a href="#/explore" className="nav-science" onClick={() => useMissionStore.getState().setAudienceMode('simple')}>Open workspace</a><ThemeToggle /></div>
      </nav>
      <nav className="topic-nav" aria-label="Page sections">{NAV_LINKS.map(([label, href]) => <a href={href} key={href}>{label}</a>)}<span>NASA SPACE APPS 2026 ? INDEPENDENT PROJECT</span></nav>
    </header>
    <main id="landing-content"><LandingPage /></main>
    <footer className="agency-footer">
      <div className="page-container footer-grid">
        <div className="footer-intro"><span className="footer-wordmark">GeoSAR Drishti</span><h2>A different perspective.<br />A better understanding.</h2><p>Exploring our changing Earth through radar, open science and accessible tools.</p></div>
        <div><h3>Explore</h3>{NAV_LINKS.map(([label, href]) => <a href={href} key={href}>{label}</a>)}</div>
        <div><h3>Open science</h3><a href="https://www.nasa.gov/" target="_blank" rel="noreferrer">NASA ↗</a><a href="https://nisar.jpl.nasa.gov/" target="_blank" rel="noreferrer">NISAR mission ↗</a><a href="https://www.earthdata.nasa.gov/" target="_blank" rel="noreferrer">NASA Earthdata ↗</a><a href="https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti" target="_blank" rel="noreferrer">Project source ↗</a></div>
      </div>
      <div className="page-container footer-fineprint"><p>Built by Team InfoVerse Cosmos for NASA Space Apps Challenge 2026, “Dancing with the SARs”. Independent participant project; not endorsed by NASA or ISRO. Water layers are radar-derived indications for field inspection, not confirmed flood, depth or damage measurements.</p><p>Earth image: NASA Earth Observatory / Robert Simmon, Suomi NPP VIIRS / NOAA. <a href="/images/CREDITS.md">Image &amp; font credits</a></p></div>
    </footer>
  </div>;
}
