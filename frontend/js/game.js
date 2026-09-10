// Game page controller: board + keyboard + info drawer + result banner.

import { api } from '/js/api.js';
import { State } from '/js/state.js';
import { setAvatar } from '/js/avatar.js';
import { buildBoard, setTypedRow, revealRow, shakeRow, pixelBurst } from '/js/board.js';
import { buildKeyboard, updateKeyStates, flashKeyByChar } from '/js/keyboard.js';

const boardEl = document.getElementById('board');
const kbEl = document.getElementById('keyboard');
const drawerEl = document.getElementById('drawer');
const drawerBody = document.getElementById('drawer-body');
const drawerWord = document.getElementById('drawer-word');
const drawerSource = document.getElementById('drawer-source');
const drawerTitle = document.getElementById('drawer-title');
const resultBanner = document.getElementById('result-banner');
const langChip = document.getElementById('lang-chip');
const difficultyChip = document.getElementById('difficulty-chip');
const infoBtn = document.getElementById('info-btn');
const attemptsValue = document.getElementById('attempts-value');
const lengthValue = document.getElementById('length-value');
const profileNameEl = document.getElementById('profile-name');
const topbarAvatar = document.getElementById('topbar-avatar');

const state = {
  game: null,
  profile: null,
  currentRow: 0,
  currentGuess: '',
  cols: 5,
  rows: 6,
  drawerOpen: window.innerWidth > 900,
  submitting: false,
};

// Language-aware casing.
// Turkish has a paired i/İ (dotted) and ı/I (dotless). JS's default
// toUpperCase()/toLowerCase() use English rules and mangle these — the
// locale-aware variants get it right. When the game is Turkish, route
// display + input through the tr-TR locale.
function up(s) {
  if (s == null) return s;
  const lang = state.game && state.game.language;
  return lang === 'tr' ? String(s).toLocaleUpperCase('tr-TR') : String(s).toUpperCase();
}
function low(s) {
  if (s == null) return s;
  const lang = state.game && state.game.language;
  return lang === 'tr' ? String(s).toLocaleLowerCase('tr-TR') : String(s).toLowerCase();
}

function isDrawerBottom() { return window.innerWidth <= 900; }
function openDrawer() { drawerEl.classList.add('is-open'); state.drawerOpen = true; }
function closeDrawer() { drawerEl.classList.remove('is-open'); state.drawerOpen = false; }
function toggleDrawer() { state.drawerOpen ? closeDrawer() : openDrawer(); }

function updateAttemptsLeft() {
  if (!state.game) { attemptsValue.textContent = 0; return; }
  const left = Math.max(0, state.game.attempts_allowed - state.game.attempts_used);
  const prev = Number(attemptsValue.textContent);
  attemptsValue.textContent = left;

  // Reactive coloring: green → warning (yellow) → danger (red pulse).
  const pill = document.getElementById('attempts-pill');
  if (pill) {
    pill.classList.remove('is-warning', 'is-danger');
    if (left === 1) pill.classList.add('is-danger');
    else if (left <= 2) pill.classList.add('is-warning');
    if (prev !== left) {
      pill.classList.remove('did-change');
      // Trigger reflow so the animation restarts.
      void pill.offsetWidth;
      pill.classList.add('did-change');
    }
  }
}

function updateHeader() {
  langChip.textContent = state.game.language.toUpperCase();
  langChip.classList.add(`chip-${state.game.language}`);
  difficultyChip.textContent = state.game.difficulty.toUpperCase();
  lengthValue.textContent = state.game.word_length;
}

function renderMeaning(payload) {
  drawerBody.innerHTML = '';
  drawerEl.classList.add('is-populated');
  drawerWord.textContent = up(payload.word);
  const src = payload.source_label + (payload.from_cache ? ' · cached' : '');
  drawerSource.textContent = src;

  if (payload.phonetic) {
    const p = document.createElement('div');
    p.className = 'small muted mono';
    p.textContent = payload.phonetic;
    drawerBody.appendChild(p);
  }
  if (payload.audio_url) {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = payload.audio_url;
    audio.style.width = '100%';
    audio.style.marginTop = '8px';
    drawerBody.appendChild(audio);
  }
  const entries = payload.entries || [];
  if (!entries.length && !(payload.extras && (payload.extras.similar || payload.extras.compounds))) {
    const empty = document.createElement('div');
    empty.className = 'drawer-empty';
    empty.textContent = 'No definition found for this word.';
    drawerBody.appendChild(empty);
    return;
  }
  for (const e of entries) {
    const wrap = document.createElement('div');
    wrap.className = 'entry';
    if (e.part_of_speech) {
      const pos = document.createElement('div');
      pos.className = 'pos';
      pos.textContent = e.part_of_speech;
      wrap.appendChild(pos);
    }
    if (e.definition) {
      const d = document.createElement('div');
      d.className = 'definition';
      d.textContent = e.definition;
      wrap.appendChild(d);
    }
    if (e.example) {
      const ex = document.createElement('div');
      ex.className = 'example';
      ex.textContent = `“${e.example}”`;
      wrap.appendChild(ex);
    }
    if (e.synonyms && e.synonyms.length) {
      const syn = document.createElement('div');
      syn.className = 'synonyms';
      for (const s of e.synonyms.slice(0, 8)) {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = s;
        syn.appendChild(chip);
      }
      wrap.appendChild(syn);
    }
    drawerBody.appendChild(wrap);
  }
  const extras = payload.extras || {};
  if (extras.compounds && extras.compounds.length) {
    const h = document.createElement('div');
    h.className = 'pos';
    h.textContent = 'Compounds';
    drawerBody.appendChild(h);
    const list = document.createElement('div');
    list.className = 'synonyms';
    for (const c of extras.compounds.slice(0, 8)) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = c;
      list.appendChild(chip);
    }
    drawerBody.appendChild(list);
  }
  if (extras.similar && extras.similar.length) {
    const h = document.createElement('div');
    h.className = 'pos';
    h.textContent = 'Similar';
    drawerBody.appendChild(h);
    const list = document.createElement('div');
    list.className = 'synonyms';
    for (const c of extras.similar.slice(0, 8)) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = c;
      list.appendChild(chip);
    }
    drawerBody.appendChild(list);
  }
}

async function fetchMeaningTarget() {
  // During active game: last submitted guess. After: the answer.
  if (!state.game) return null;
  if (state.game.status === 'active') {
    const last = state.game.guesses[state.game.guesses.length - 1];
    return last ? last.guess : null;
  }
  return state.game.answer;
}

async function openMeaning() {
  if (isDrawerBottom()) openDrawer();
  const target = await fetchMeaningTarget();
  if (!target) {
    drawerBody.innerHTML = '<div class="drawer-empty">Submit a guess first, then tap (i) to see what that word means.</div>';
    drawerWord.textContent = '—';
    drawerSource.textContent = '';
    return;
  }
  drawerTitle.textContent = state.game.status === 'active' ? 'Meaning of your guess' : 'Meaning of the answer';
  drawerBody.innerHTML = '<div class="drawer-empty">Loading …</div>';
  drawerWord.textContent = up(target);
  drawerSource.textContent = '';
  try {
    const payload = await api.meaning(state.game.language, target, state.profile.id);
    renderMeaning(payload);
  } catch (e) {
    drawerBody.innerHTML = `<div class="drawer-empty">Couldn't load meaning: ${e.message}</div>`;
  }
}

function showResult() {
  const g = state.game;
  const banner = resultBanner;
  banner.classList.remove('hidden', 'win', 'lose');
  if (g.status === 'won') {
    banner.classList.add('win');
    banner.innerHTML = `You solved it. <span class="answer">${up(g.answer)}</span><div class="actions">
      <button class="btn btn-secondary" id="reveal-meaning">See meaning</button>
      <a href="/" class="btn btn-primary">New game</a>
      <a href="/profile" class="btn btn-ghost">Profile →</a>
    </div>`;
    pixelBurst();
  } else if (g.status === 'lost') {
    banner.classList.add('lose');
    banner.innerHTML = `The word was <span class="answer">${up(g.answer)}</span>.<div class="actions">
      <button class="btn btn-secondary" id="reveal-meaning">See meaning</button>
      <a href="/" class="btn btn-primary">New game</a>
      <a href="/profile" class="btn btn-ghost">Profile →</a>
    </div>`;
  }
  const rm = document.getElementById('reveal-meaning');
  if (rm) rm.addEventListener('click', openMeaning);
}

function pushLetter(ch) {
  if (state.game.status !== 'active') return;
  if (state.currentGuess.length >= state.cols) return;
  const lower = low(ch);
  state.currentGuess += lower;
  setTypedRow(boardEl, state.currentRow, state.currentGuess.split(''), state.cols);
  flashKeyByChar(kbEl, lower);
}
function popLetter() {
  if (state.game.status !== 'active') return;
  if (state.currentGuess.length === 0) return;
  state.currentGuess = state.currentGuess.slice(0, -1);
  setTypedRow(boardEl, state.currentRow, state.currentGuess.split(''), state.cols);
  flashKeyByChar(kbEl, 'BACK');
}

async function submitGuess() {
  if (state.game.status !== 'active' || state.submitting) return;
  if (state.currentGuess.length !== state.cols) {
    shakeRow(boardEl);
    return;
  }
  state.submitting = true;
  try {
    const res = await api.submitGuess(state.game.game_id, state.currentGuess);
    revealRow(boardEl, state.currentRow, state.currentGuess.split(''), res.result);
    updateKeyStates(kbEl, state.currentGuess, res.result);
    state.game.attempts_used = res.attempts_used;
    state.game.status = res.status;
    state.game.guesses.push({ guess: state.currentGuess, result: res.result });
    if (res.answer) state.game.answer = res.answer;
    state.currentRow += 1;
    state.currentGuess = '';
    updateAttemptsLeft();
    if (res.status !== 'active') {
      setTimeout(showResult, 800);
    }
  } catch (e) {
    if (e.status === 400 && /not in dictionary/i.test(e.message)) {
      shakeRow(boardEl);
      flashDrawer(`"${state.currentGuess}" is not in the ${state.game.language.toUpperCase()} word list.`);
    } else if (e.status === 400 && /game not found/i.test(e.message)) {
      // The server has no record of this game (fresh DB or purged session).
      // Clear stale local state and send the player back to Welcome so they
      // can start a new one without a jarring alert.
      State.set({ last_game_id: null });
      flashDrawer('That game expired. Restarting …');
      setTimeout(() => { window.location.href = '/'; }, 900);
    } else {
      alert(e.message);
    }
  } finally {
    state.submitting = false;
  }
}

function flashDrawer(msg) {
  const existing = document.getElementById('flash-note');
  if (existing) existing.remove();
  const note = document.createElement('div');
  note.id = 'flash-note';
  note.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);background:var(--surface-3);border:1px solid var(--border-strong);padding:8px 14px;border-radius:6px;z-index:10;font-family:var(--font-mono);font-size:13px';
  note.textContent = msg;
  document.body.appendChild(note);
  setTimeout(() => note.remove(), 1600);
}

function bindKeyboardEvents() {
  document.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'Enter') { e.preventDefault(); return submitGuess(); }
    if (e.key === 'Backspace') { e.preventDefault(); return popLetter(); }
    if (/^[a-zA-ZçğıİöşüßäÖöÄäÜü]$/.test(e.key)) {
      e.preventDefault();
      // Turkish input: Shift+i must land as dotted 'i' and Shift+ı as dotless 'I'
      // — but only in Turkish. In English/German, plain 'I' must lowercase to 'i'.
      let ch;
      if (state.game && state.game.language === 'tr') {
        if (e.key === 'İ') ch = 'i';
        else if (e.key === 'I') ch = 'ı';
        else ch = e.key.toLocaleLowerCase('tr-TR');
      } else {
        ch = e.key.toLowerCase();
      }
      pushLetter(ch);
    }
  });
}

function onKbKey(key) {
  if (key === 'ENTER') return submitGuess();
  if (key === 'BACK') return popLetter();
  pushLetter(key);
}

function replayHistory(guesses) {
  for (let i = 0; i < guesses.length; i++) {
    const g = guesses[i];
    for (let c = 0; c < g.guess.length; c++) {
      const tile = boardEl.querySelector(`.tile[data-row="${i}"][data-col="${c}"]`);
      if (!tile) continue;
      tile.textContent = up(g.guess[c]);
      tile.classList.add(`is-${g.result[c]}`);
    }
    updateKeyStates(kbEl, g.guess, g.result);
  }
  state.currentRow = guesses.length;
}

async function init() {
  const gameId = State.lastGameId();
  if (!gameId) {
    window.location.href = '/';
    return;
  }
  try {
    state.game = await api.getGame(gameId);
  } catch (e) {
    console.warn('Game not found, clearing local state and redirecting home', e);
    // Purge the stale id — otherwise the next visit loops right back here.
    State.set({ last_game_id: null });
    window.location.href = '/';
    return;
  }
  const profileId = State.activeProfileId() || state.game.profile_id;
  try {
    state.profile = await api.getProfile(profileId);
  } catch (e) {
    // Fresh DB — profile purged too. Rebuild from the game's owner id.
    console.warn('Profile not found, using game.profile_id', e);
    State.setActiveProfileId(state.game.profile_id);
    state.profile = await api.getProfile(state.game.profile_id).catch(() => ({
      id: state.game.profile_id,
      name: 'Player',
      avatar_config: {},
    }));
  }

  state.cols = state.game.word_length;
  state.rows = state.game.attempts_allowed;

  // Tell the browser this content is in the game's language so CSS
  // `text-transform: uppercase` (on tiles, keys, drawer word, answer
  // banner) applies Turkish-correct casing: i → İ, ı → I.
  const gameMain = document.querySelector('.game-main');
  const kbSection = document.querySelector('.keyboard');
  if (gameMain) gameMain.setAttribute('lang', state.game.language);
  if (kbSection) kbSection.setAttribute('lang', state.game.language);

  updateHeader();
  updateAttemptsLeft();
  profileNameEl.textContent = state.profile.name;
  setAvatar(topbarAvatar, state.profile.avatar_config);

  buildBoard(boardEl, state.rows, state.cols);
  buildKeyboard(kbEl, state.game.language, onKbKey);
  bindKeyboardEvents();
  replayHistory(state.game.guesses || []);
  if (state.game.status !== 'active') showResult();

  infoBtn.addEventListener('click', openMeaning);
  const handle = drawerEl.querySelector('.drawer-handle');
  if (handle) handle.addEventListener('click', toggleDrawer);
}

init();
