/* Toasts and screen-reader announcements.
 *
 * Replaces `alert(e.message)`, which was the app's real error UI in two places
 * and put raw backend English in a modal that blocks the whole page, and a
 * `cssText`-styled div with no class, no animation and no aria-live.
 */

let region = null;
let liveRegion = null;

function ensureRegions() {
  if (!region) {
    region = document.createElement('div');
    region.className = 'toast-region';
    // status, not alert: alert interrupts whatever the screen reader is
    // saying, which is wrong for "not in the word list" mid-game.
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    document.body.appendChild(region);
  }
  if (!liveRegion) {
    liveRegion = document.createElement('div');
    liveRegion.className = 'visually-hidden';
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    document.body.appendChild(liveRegion);
  }
}

/**
 * Show a message. `tone` is 'info' | 'error' | 'success'.
 * Returns a function that dismisses it early.
 */
export function toast(message, { tone = 'info', duration = 3200 } = {}) {
  ensureRegions();
  const el = document.createElement('div');
  el.className = 'toast';
  el.dataset.tone = tone;
  el.textContent = message;
  region.appendChild(el);

  const remove = () => {
    if (!el.isConnected) return;
    el.classList.add('is-leaving');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    // Belt and braces: if the animation is suppressed by reduced motion the
    // animationend event never fires.
    setTimeout(() => el.remove(), 400);
  };

  const timer = setTimeout(remove, duration);
  return () => {
    clearTimeout(timer);
    remove();
  };
}

/**
 * Announce to assistive tech without showing anything.
 * Used for guess results, which were previously not announced at all — the
 * board conveyed everything through background-color and nothing else.
 */
export function announce(message) {
  ensureRegions();
  // Clearing first forces a re-announcement when the same text repeats.
  liveRegion.textContent = '';
  window.requestAnimationFrame(() => {
    liveRegion.textContent = message;
  });
}
