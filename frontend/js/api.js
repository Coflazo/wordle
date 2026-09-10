// Thin wrapper around fetch for the /api namespace.
const BASE = '';

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      if (j && j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return await res.json();
}

export const api = {
  ping: () => req('GET', '/api/ping'),

  listProfiles: () => req('GET', '/api/profiles'),
  createProfile: (body) => req('POST', '/api/profiles', body),
  getProfile: (id) => req('GET', `/api/profiles/${id}`),
  updateProfile: (id, body) => req('PUT', `/api/profiles/${id}`, body),

  startGame: (body) => req('POST', '/api/games/start', body),
  getGame: (id) => req('GET', `/api/games/${id}`),
  submitGuess: (id, guess) => req('POST', `/api/games/${id}/guess`, { guess }),
  giveUp: (id) => req('POST', `/api/games/${id}/give-up`),

  meaning: (lang, word, profileId) => {
    const q = profileId ? `?profile_id=${profileId}` : '';
    return req('GET', `/api/meaning/${lang}/${encodeURIComponent(word)}${q}`);
  },

  dashboard: (profileId, language) => {
    const q = language ? `?language=${language}` : '';
    return req('GET', `/api/stats/${profileId}${q}`);
  },
};
