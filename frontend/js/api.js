/* HTTP layer.
 *
 * Adds what the previous 45-line version did not have: a timeout, retries for
 * idempotent calls, and structured errors. A hung backend used to hang the UI
 * forever with the input lock still held and no way out.
 */

const BASE = '';
const DEFAULT_TIMEOUT = 12000;
const RETRY_STATUSES = new Set([502, 503, 504]);

export class ApiError extends Error {
  constructor({ status, code, message, params }) {
    super(message || code || 'request failed');
    this.name = 'ApiError';
    this.status = status;
    // A stable code, so callers switch on `err.code` instead of regex-matching
    // the server's prose. The old frontend tested /not in dictionary/i, which
    // broke on any rewording and made error text untranslatable.
    this.code = code || 'generic';
    this.params = params || {};
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function parseError(res) {
  let code = 'generic';
  let message = res.statusText;
  let params = {};
  try {
    const body = await res.json();
    const detail = body && body.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object') {
      code = detail.code || code;
      message = detail.message || message;
      params = detail.params || {};
    } else if (Array.isArray(body)) {
      message = JSON.stringify(body);
    }
  } catch {
    /* a non-JSON body, keep the status text */
  }
  if (code === 'generic') {
    if (res.status === 404) code = 'not_found';
    if (res.status === 429) code = 'rate_limited';
    if (res.status >= 500) code = 'internal_error';
  }
  return new ApiError({ status: res.status, code, message, params });
}

async function req(method, path, body, options = {}) {
  const { timeout = DEFAULT_TIMEOUT, retries = method === 'GET' ? 2 : 0, signal } = options;

  for (let attempt = 0; ; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const onAbort = () => controller.abort();
    if (signal) signal.addEventListener('abort', onAbort, { once: true });

    try {
      const res = await fetch(BASE + path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        const error = await parseError(res);
        if (attempt < retries && RETRY_STATUSES.has(res.status)) {
          await sleep(200 * 2 ** attempt);
          continue;
        }
        throw error;
      }
      if (res.status === 204) return null;
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      // The caller cancelled deliberately; do not dress it up as a failure.
      if (signal && signal.aborted) throw err;
      const timedOut = err.name === 'AbortError';
      if (attempt < retries) {
        await sleep(200 * 2 ** attempt);
        continue;
      }
      throw new ApiError({
        status: 0,
        code: timedOut ? 'timeout' : 'offline',
        message: err.message,
      });
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', onAbort);
    }
  }
}

export const api = {
  ping: () => req('GET', '/api/ping'),

  listProfiles: () => req('GET', '/api/profiles'),
  getProfile: (id) => req('GET', `/api/profiles/${id}`),
  createProfile: (payload) => req('POST', '/api/profiles', payload),
  updateProfile: (id, payload) => req('PATCH', `/api/profiles/${id}`, payload),
  deleteProfile: (id) => req('DELETE', `/api/profiles/${id}`),

  startGame: (payload) => req('POST', '/api/games/start', payload),
  // The browser's offset, so the puzzle rolls over at the player's midnight
  // rather than the server's.
  daily: (profileId, language) => req('POST',
    `/api/games/daily?profile_id=${profileId}&language=${language}`
    + `&tz_offset_minutes=${-new Date().getTimezoneOffset()}`),
  getGame: (id, theme) => req('GET', `/api/games/${id}${theme ? `?theme=${theme}` : ''}`),
  // No retry on a guess: replaying a turn that did land would consume two.
  submitGuess: (id, guess) => req('POST', `/api/games/${id}/guess`, { guess }, { retries: 0 }),
  giveUp: (id) => req('POST', `/api/games/${id}/give-up`, undefined, { retries: 0 }),
  hint: (id, topK = 3) => req('GET', `/api/games/${id}/hint?top_k=${topK}`, undefined, {
    timeout: 20000,
  }),

  meaning: (language, word, profileId, options) => {
    const query = profileId ? `?profile_id=${profileId}` : '';
    return req('GET', `/api/meaning/${language}/${encodeURIComponent(word)}${query}`, undefined, {
      timeout: 20000,
      ...options,
    });
  },

  dashboard: (profileId, language, options) => {
    const query = language ? `?language=${language}` : '';
    return req('GET', `/api/stats/${profileId}${query}`, undefined, options);
  },

  flags: (profileId) =>
    req('GET', `/api/flags${profileId ? `?profile_id=${profileId}` : ''}`),
  sendEvents: (payload) => req('POST', '/api/events', payload, { retries: 0, timeout: 4000 }),
  experiments: () => req('GET', '/api/experiments/results'),
};
