// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useMissionStore } from '@/store/useMissionStore.js';
import LandingLayout from '@/components/landing/LandingLayout.jsx';

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('landing navigation and theme', () => {
  it('keeps an Earth photograph and hides unavailable animation controls without WebGL', () => {
    render(<LandingLayout />);
    expect(screen.getByRole('img', { name: 'Earth viewed from space' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Pause Earth rotation' })).toBeNull();
  });
  it('closes the Explore navigation on Escape and returns focus to its trigger', () => {
    render(<LandingLayout />);
    const trigger = screen.getByRole('button', { name: /Explore/ });
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    const menuLink = screen.getAllByRole('link', { name: /Radar in action/ })[0];
    menuLink.focus();
    fireEvent.keyDown(menuLink, { key: 'Escape' });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('closes navigation after selecting a section or clicking outside it', () => {
    render(<LandingLayout />);
    const trigger = screen.getByRole('button', { name: /Explore/ });
    fireEvent.click(trigger);
    fireEvent.click(document.querySelector('.explore-dropdown a'));
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(trigger);
    fireEvent.pointerDown(screen.getByRole('heading', { level: 1 }));
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('defaults to the light editorial theme and preserves a selected dark theme on return', () => {
    localStorage.removeItem('geosar-landing-theme');
    const view = render(<LandingLayout />);
    expect(document.querySelector('.landing').classList.contains('light')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.querySelector('.landing').classList.contains('light')).toBe(false);
    view.unmount();
    render(<LandingLayout />);
    expect(document.querySelector('.landing').classList.contains('light')).toBe(false);
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeTruthy();
    localStorage.removeItem('geosar-landing-theme');
  });
});

describe('landing experience selection', () => {
  it('opens the workspace directly from the hero in simple mode without a mode-selection step', () => {
    useMissionStore.getState().setAudienceMode('scientific');
    render(<LandingLayout />);
    const launch = screen.getByRole('link', { name: 'Start exploring' });
    expect(launch.getAttribute('href')).toBe('#/explore');
    fireEvent.click(launch);
    expect(useMissionStore.getState().audienceMode).toBe('simple');
    expect(useMissionStore.getState().basemap).toBe('satellite');
  });
  it('removes the experience selector and field guide without leaving broken section links', () => {
    render(<LandingLayout />);
    expect(screen.queryByRole('heading', { name: 'One Earth. Two ways to explore.' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'A little context. A clearer picture.' })).toBeNull();
    expect(screen.queryByRole('group', { name: 'Choose your experience' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Explore/ }));
    const workspaceLinks = screen.getAllByRole('link').filter(link => link.getAttribute('href') === '#/explore');
    expect(workspaceLinks).toHaveLength(1);
    expect(workspaceLinks[0].textContent).toContain('Start exploring');
    for (const link of screen.getAllByRole('link')) {
      const href = link.getAttribute('href');
      if (href?.startsWith('#') && !href.startsWith('#/')) {
        expect(document.getElementById(href.slice(1)), `Missing target for ${href}`).toBeTruthy();
      }
    }
  });
});

describe('landing case studies and walkthrough', () => {
  it('opens a browser-viewable PDF in a new tab and keeps the PowerPoint download separate', () => {
    render(<LandingLayout />);
    const preview = screen.getByRole('link', { name: 'Open GeoSAR Drishti presentation preview in a new tab' });
    expect(preview.getAttribute('href')).toBe('/preview/GeoSAR_Drishti_Judging_Presentation.pdf');
    expect(preview.getAttribute('target')).toBe('_blank');
    expect(preview.hasAttribute('download')).toBe(false);
    expect(screen.getByRole('link', { name: 'Download PowerPoint' }).hasAttribute('download')).toBe(true);
  });

  it('shows all six supplied Assam images with links to their full resolution', () => {
    render(<LandingLayout />);
    for (let number = 1; number <= 6; number++) {
      const image = document.querySelector(`img[src="/images/projectdemo${number}.jpeg"]`);
      expect(image).toBeTruthy();
      expect(image.closest('a').getAttribute('href')).toBe(`/images/projectdemo${number}.jpeg`);
    }
    expect(screen.getByText(/external reference case/)).toBeTruthy();
  });

  it('maximizes the YouTube walkthrough and restores focus when closed', () => {
    render(<LandingLayout />);
    const dialog = document.querySelector('dialog');
    const showModal = dialog.showModal = vi.fn(() => dialog.setAttribute('open', ''));
    const close = dialog.close = vi.fn(() => { dialog.removeAttribute('open'); dialog.dispatchEvent(new Event('close')); });
    const trigger = screen.getByRole('button', { name: 'Maximize video' });
    fireEvent.click(trigger);
    expect(showModal).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: /Close video/ }));
    expect(close).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(trigger);
    const frame = document.querySelector('.project-media-grid iframe');
    expect(frame.getAttribute('src')).toBe('https://www.youtube-nocookie.com/embed/mqZ5vd-t40s');
    expect(frame.hasAttribute('allowfullscreen')).toBe(true);
  });
});
