import { useEffect, useRef, useState } from 'react';
import LandingPage from './LandingPage.jsx';
import { ThemeToggle } from './ThemeToggle.jsx';
import '@/landing.css';

const NAV_LINKS = [
  ['Start exploring', '#start', 'Choose your experience and study area'],
  ['Radar in action', '#radar', 'See a before-and-after observation'],
  ['The science', '#about-sar', 'Understand how radar reveals water'],
  ['Field guide', '#field-guide', 'Plain-language answers to your questions'],
  ['Our team', '#team', 'Meet the people behind GeoSAR Drishti'],
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
        <a href="#/" className="agency-wordmark" aria-label="GeoSAR Drishti home"><span className="orbit-mark" aria-hidden="true">G<span /></span><span>GeoSAR<span className="wordmark-subtitle">DRISHTI</span></span></a>
        <div className="agency-nav-actions"><a href="#about-sar" className="nav-science">Mission &amp; Science</a><ThemeToggle /><a href="#/explore" className="nav-launch">Launch map <span className="arrow-disc" aria-hidden="true">↗</span></a></div>
      </nav>
      <nav className="topic-nav" aria-label="Page sections"><a href="#start">Explore Earth</a><a href="#radar">Radar imagery</a><a href="#about-sar">Our science</a><a href="#field-guide">Learning resources</a><a href="#team">Our team</a><span>NASA SPACE APPS 2026 · INDEPENDENT PROJECT</span></nav>
    </header>
    <main id="landing-content"><LandingPage /></main>
    <footer className="agency-footer">
      <div className="page-container footer-grid">
        <div className="footer-intro"><span className="footer-wordmark">GeoSAR Drishti</span><h2>A different perspective.<br />A better understanding.</h2><p>Exploring our changing Earth through radar, open science and accessible tools.</p><a href="#start" className="editorial-link">Begin your exploration <span className="arrow-disc" aria-hidden="true">↗</span></a></div>
        <div><h3>Explore</h3>{NAV_LINKS.map(([label, href]) => <a href={href} key={href}>{label}</a>)}</div>
        <div><h3>Open science</h3><a href="https://www.nasa.gov/" target="_blank" rel="noreferrer">NASA ↗</a><a href="https://nisar.jpl.nasa.gov/" target="_blank" rel="noreferrer">NISAR mission ↗</a><a href="https://www.earthdata.nasa.gov/" target="_blank" rel="noreferrer">NASA Earthdata ↗</a><a href="https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti" target="_blank" rel="noreferrer">Project source ↗</a></div>
      </div>
      <div className="page-container footer-fineprint"><p>Built by Team InfoVerse Cosmos for NASA Space Apps Challenge 2026, “Dancing with the SARs”. Independent participant project; not endorsed by NASA or ISRO. Water layers are radar-derived indications for field inspection, not confirmed flood, depth or damage measurements.</p><p>Earth image: NASA Earth Observatory / Robert Simmon, Suomi NPP VIIRS / NOAA. <a href="/images/CREDITS.md">Image &amp; font credits</a></p></div>
    </footer>
  </div>;
}
