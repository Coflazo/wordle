// Local session state persisted to localStorage.
const KEY = 'oflaz-wordle:v1';

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    return JSON.parse(raw) || {};
  } catch (_) {
    return {};
  }
}

function save(patch) {
  const next = { ...load(), ...patch };
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export const State = {
  get: load,
  set: save,
  clear: () => localStorage.removeItem(KEY),

  activeProfileId: () => load().active_profile_id ?? null,
  setActiveProfileId: (id) => save({ active_profile_id: id }),

  sessionLanguage: () => load().session_language || 'en',
  sessionDifficulty: () => load().session_difficulty || 'classic',
  sessionCharacter: () => load().session_character || null,
  lastGameId: () => load().last_game_id || null,
};
