/* Local session state.
 *
 * One parse per page rather than one per getter — the old version re-read and
 * re-parsed localStorage on every accessor, five times during welcome-page
 * init alone. Writes are guarded, so Safari private browsing (where setItem
 * throws) degrades to an in-memory session instead of throwing after a game
 * has already been created server-side.
 */

const KEY = 'oflaz-wordle:v2';

let cache = null;
let writable = true;

function load() {
  if (cache) return cache;
  try {
    cache = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
  } catch {
    cache = {};
  }
  return cache;
}

function persist() {
  if (!writable) return;
  try {
    localStorage.setItem(KEY, JSON.stringify(cache));
  } catch {
    // Quota exceeded or private browsing. Keep running from memory; losing the
    // pointer to the current game is far better than throwing after the server
    // already created it, which is what used to happen.
    writable = false;
  }
}

export const State = {
  get: (key, fallback = null) => {
    const value = load()[key];
    return value === undefined ? fallback : value;
  },

  set(patch) {
    Object.assign(load(), patch);
    persist();
    return cache;
  },

  clear(...keys) {
    const data = load();
    for (const key of keys) delete data[key];
    persist();
  },

  activeProfileId: () => State.get('active_profile_id'),
  lastGameId: () => State.get('last_game_id'),
  sessionLanguage: () => State.get('session_language', 'en'),
  sessionDifficulty: () => State.get('session_difficulty', 'classic'),
  sessionLength: () => State.get('session_length', null),
  anonymousId() {
    let id = State.get('anonymous_id');
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
      State.set({ anonymous_id: id });
    }
    return id;
  },
};

/* Two tabs used to silently overwrite each other's last write. Reload the
 * cache when another tab changes it so at least reads stay honest. */
window.addEventListener('storage', (event) => {
  if (event.key === KEY) {
    cache = null;
    document.dispatchEvent(new CustomEvent('statechange'));
  }
});
