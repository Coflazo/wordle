/* Theme selection.
 *
 * Four themes plus "system". The value is stamped on <html data-theme> so the
 * token layer can override in both directions, and `color-scheme` is set so
 * native controls follow — the old sheet had none, which is why the <select>
 * dropdowns and the <audio> player in the meaning drawer rendered light against
 * a dark interface.
 */

const KEY = 'oflaz-wordle:theme';
export const THEMES = ['system', 'dark', 'light', 'contrast', 'colorblind'];

let current = 'system';

function stored() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function getTheme() {
  return current;
}

export function setTheme(theme) {
  current = THEMES.includes(theme) ? theme : 'system';
  document.documentElement.setAttribute('data-theme', current);
  try {
    localStorage.setItem(KEY, current);
  } catch {
    /* private browsing */
  }
  document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: current } }));
  return current;
}

export function initTheme(preferred) {
  return setTheme(preferred && preferred !== 'system' ? preferred : stored() || 'system');
}

/**
 * True when motion should be suppressed. Unlike the previous implementation
 * this is read live rather than captured once at load, so toggling the OS
 * setting takes effect without a reload.
 */
const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

export function prefersReducedMotion() {
  return reducedQuery.matches;
}

export function onReducedMotionChange(handler) {
  reducedQuery.addEventListener('change', (event) => handler(event.matches));
}
