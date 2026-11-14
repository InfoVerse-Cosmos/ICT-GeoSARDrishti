// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ExploreGuide, { FieldGuide } from '@/components/landing/ExploreGuide.jsx';
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
    const menuLink = screen.getAllByRole('link', { name: /Start exploring/ })[0];
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
    const launch = screen.getByRole('link', { name: 'Explore the water story' });
    expect(launch.getAttribute('href')).toBe('#/explore');
    fireEvent.click(launch);
    expect(useMissionStore.getState().audienceMode).toBe('simple');
    expect(useMissionStore.getState().basemap).toBe('satellite');
  });
  it('opens the scientific workspace with the selected area and matching basemap', () => {
    render(<ExploreGuide />);
    fireEvent.click(screen.getByRole('button', { name: 'Researchers & analysts' }));
    fireEvent.change(screen.getByLabelText('Choose a study area'), { target: { value: 'aoi_nagpur_kanhan' } });
    const launch = screen.getByRole('link', { name: /Open scientific workspace/ });
    expect(launch.getAttribute('href')).toBe('#/explore');
    fireEvent.click(launch);
    expect(useMissionStore.getState().audienceMode).toBe('scientific');
    expect(useMissionStore.getState().basemap).toBe('dark');
    expect(useMissionStore.getState().activeAoiId).toBe('aoi_nagpur_kanhan');
  });

  it('lets a returning scientist start in simple mode', () => {
    useMissionStore.getState().setAudienceMode('scientific');
    render(<ExploreGuide />);
    fireEvent.click(screen.getByRole('link', { name: /Explore in simple mode/ }));
    expect(useMissionStore.getState().audienceMode).toBe('simple');
    expect(useMissionStore.getState().basemap).toBe('satellite');
    expect(useMissionStore.getState().activeAoiId).toBe('aoi_assam_majuli');
  });

  it('explains observation frequency without claiming days of flooding', () => {
    render(<FieldGuide />);
    expect(screen.getByText(/This does not mean six days of flooding/)).toBeTruthy();
    expect(screen.getByText(/does not measure flood depth or confirm damage/)).toBeTruthy();
  });
});
