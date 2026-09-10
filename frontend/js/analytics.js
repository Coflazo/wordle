/* Local event tracking and experiment flags.
 *
 * Everything is posted to this app's own backend and stored in the local
 * SQLite file. No third party, no network beyond localhost — the same promise
 * the rest of the app makes.
 *
 * Events are queued and flushed in batches so a burst of keystrokes does not
 * become a burst of requests, and the queue is flushed on pagehide via
 * sendBeacon so the last events of a session are not lost.
 */

import { api } from '/js/api.js';
import { State } from '/js/state.js';

const FLUSH_INTERVAL = 5000;
const MAX_QUEUE = 40;

let queue = [];
let flushTimer = null;
let flags = {};

export function getFlag(key, fallback = null) {
  return Object.prototype.hasOwnProperty.call(flags, key) ? flags[key] : fallback;
}

export function allFlags() {
  return { ...flags };
}

/** Fetch arm assignments. Failing is not fatal — everything falls back. */
export async function initFlags(profileId) {
  try {
    const payload = await api.flags(profileId);
    flags = payload.assignments || {};
  } catch {
    flags = {};
  }
  return flags;
}

export function track(name, props = {}, gameId = null) {
  queue.push({ name, game_id: gameId, props: { ...props, variant: flags } });
  if (queue.length >= MAX_QUEUE) {
    flush();
  } else if (!flushTimer) {
    flushTimer = setTimeout(flush, FLUSH_INTERVAL);
  }
}

export async function flush() {
  clearTimeout(flushTimer);
  flushTimer = null;
  if (!queue.length) return;

  const batch = queue.splice(0, MAX_QUEUE);
  const payload = { profile_id: State.activeProfileId(), events: batch };
  try {
    await api.sendEvents(payload);
  } catch {
    // Telemetry must never surface to the player or block anything. Drop it.
  }
}

function flushBeacon() {
  if (!queue.length || !navigator.sendBeacon) return;
  const payload = JSON.stringify({ profile_id: State.activeProfileId(), events: queue });
  navigator.sendBeacon('/api/events', new Blob([payload], { type: 'application/json' }));
  queue = [];
}

// pagehide, not unload: unload is unreliable on mobile Safari and blocks the
// back/forward cache.
window.addEventListener('pagehide', flushBeacon);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flushBeacon();
});

/* Failures the player never reports. These are the ones worth capturing. */
window.addEventListener('error', (event) => {
  track('client_error', {
    message: String(event.message || '').slice(0, 200),
    source: String(event.filename || '').slice(-80),
    line: event.lineno,
  });
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  track('client_error', {
    message: String((reason && reason.message) || reason || '').slice(0, 200),
    kind: 'unhandledrejection',
  });
});
