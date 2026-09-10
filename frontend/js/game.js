/* Game screen controller. */

import { api, ApiError } from '/js/api.js';
import { State } from '/js/state.js';
import { Board } from '/js/board.js';
import { Keyboard, keyFromEvent } from '/js/keyboard.js';
import { renderAvatar } from '/js/avatar.js';
import { announce, toast } from '/js/toast.js';
import { initFlags, getFlag, track, flush } from '/js/analytics.js';
import { initTheme } from '/js/theme.js';
import {
  applyTranslations, formatNumber, initLocale, lower, plural, setLocale, t, upper,
} from '/js/i18n.js';

const el = (id) => document.getElementById(id);

const dom = {
  board: el('board'),
  keyboard: el('keyboard'),
  statusStrip: el('status-strip'),
  lengthValue: el('stat-length'),
  attemptsPill: el('attempts-pill'),
  attemptsValue: el('stat-attempts'),
  difficultyChip: el('chip-difficulty'),
  languageChip: el('chip-language'),
  banner: el('result-banner'),
  drawer: el('drawer'),
  drawerHandle: el('drawer-handle'),
  drawerTitle: el('drawer-title'),
  drawerWord: el('drawer-word'),
  drawerBody: el('drawer-body'),
  meaningBtn: el('meaning-btn'),
  hintBtn: el('hint-btn'),
  avatar: el('topbar-avatar'),
  profileName: el('topbar-name'),
};

const session = {
  game: null,
  board: new Board(dom.board),
  keyboard: null,
  currentGuess: '',
  currentRow: 0,
  /** Held from submit until the reveal animation has fully settled. The old
   *  code released it the moment the response landed, so a second guess could
   *  be typed and submitted while the first row was still flipping. */
  busy: false,
  startedAt: 0,
};

/* ------------------------------------------------------------- rendering */

function renderStatus() {
  const game = session.game;
  const left = game.attempts_allowed - game.attempts_used;
  dom.lengthValue.textContent = formatNumber(game.word_length);
  dom.attemptsValue.textContent = formatNumber(left);
  dom.attemptsPill.dataset.tone = left <= 1 ? 'danger' : left <= 2 ? 'warning' : 'ok';
  dom.difficultyChip.textContent = t(`difficulty.${game.difficulty}`);
  dom.languageChip.textContent = t(`languages.${game.language}`);
}

function replayHistory() {
  session.board.build(session.game.word_length, session.game.attempts_allowed, session.game.language);
  session.keyboard.build(session.game.language);
  session.keyboard.reset();

  for (const entry of session.game.guesses) {
    const letters = Array.from(entry.guess);
    const row = entry.turn - 1;
    for (let c = 0; c < letters.length; c += 1) {
      const tile = session.board.tiles[row] && session.board.tiles[row][c];
      if (!tile) continue;
      tile.textContent = upper(letters[c], session.game.language);
      tile.dataset.filled = 'true';
      tile.dataset.state =
        entry.result[c] === 'green' ? 'correct' : entry.result[c] === 'yellow' ? 'present' : 'absent';
    }
    session.keyboard.applyResult(letters, entry.result);
  }
  session.currentRow = session.game.guesses.length;
  session.currentGuess = '';
}

function showResult() {
  const game = session.game;
  const won = game.status === 'won';
  const answer = upper(game.answer_display || game.answer || '', game.language);

  dom.banner.dataset.outcome = game.status;
  dom.banner.hidden = false;
  dom.banner.replaceChildren();

  const heading = document.createElement('p');
  heading.className = 'result-headline';
  heading.textContent = won ? t('game.won') : t('game.lost');

  const answerLine = document.createElement('p');
  if (!won) {
    answerLine.append(`${t('game.answerWas')} `);
  }
  const answerEl = document.createElement('span');
  answerEl.className = 'result-answer';
  answerEl.lang = game.language;
  answerEl.textContent = answer;
  answerLine.appendChild(answerEl);

  const actions = document.createElement('div');
  actions.className = 'result-actions';

  const meaningBtn = document.createElement('button');
  meaningBtn.type = 'button';
  meaningBtn.className = 'btn btn-primary';
  meaningBtn.textContent = t('game.seeMeaning');
  meaningBtn.addEventListener('click', () => openMeaning('result_banner'));

  const againBtn = document.createElement('a');
  againBtn.className = 'btn';
  againBtn.href = '/';
  againBtn.textContent = t('game.playAgain');

  const profileBtn = document.createElement('a');
  profileBtn.className = 'btn btn-ghost';
  profileBtn.href = '/profile';
  profileBtn.textContent = t('nav.profile');

  actions.append(meaningBtn, againBtn, profileBtn);
  dom.banner.append(heading, answerLine, actions);

  // Move focus so a keyboard or screen-reader user lands on the outcome
  // instead of being left somewhere in a now-dead grid, and scroll it into
  // view — on a tall board the banner could be entirely off-screen.
  dom.banner.setAttribute('tabindex', '-1');
  dom.banner.focus({ preventScroll: true });
  dom.banner.scrollIntoView({ behavior: 'smooth', block: 'center' });
  announce(`${won ? t('game.won') : t('game.lost')} ${answer}`);

  session.keyboard.setDisabled(true);
  dom.hintBtn.disabled = true;

  track('game_completed', {
    status: game.status,
    attempts_used: game.attempts_used,
    attempts_allowed: game.attempts_allowed,
    word_length: game.word_length,
    language: game.language,
    difficulty: game.difficulty,
    hints_used: game.hints_used || 0,
    duration_ms: session.startedAt ? Date.now() - session.startedAt : null,
  }, game.game_id);
  flush();

  if (!won && getFlag('meaning_on_loss') === 'auto') {
    openMeaning('auto_on_loss');
  }
}

/* ---------------------------------------------------------------- input */

function pushLetter(ch) {
  if (session.busy || session.game.status !== 'active') return;
  if (Array.from(session.currentGuess).length >= session.game.word_length) return;
  session.currentGuess += lower(ch, session.game.language);
  session.board.setTypedRow(session.currentRow, Array.from(session.currentGuess));
  session.keyboard.flashLetter(ch);
}

function popLetter() {
  if (session.busy || session.game.status !== 'active') return;
  const letters = Array.from(session.currentGuess);
  letters.pop();
  session.currentGuess = letters.join('');
  session.board.setTypedRow(session.currentRow, letters);
}

async function submitGuess() {
  const game = session.game;
  if (session.busy || game.status !== 'active') return;

  const letters = Array.from(session.currentGuess);
  if (letters.length !== game.word_length) {
    session.board.shake();
    announce(t('errors.wrong_length', { expected: game.word_length, got: letters.length }));
    track('guess_rejected', { reason: 'wrong_length', got: letters.length }, game.game_id);
    return;
  }

  session.busy = true;
  session.keyboard.setDisabled(true);
  const startedAt = performance.now();

  try {
    const res = await api.submitGuess(game.game_id, session.currentGuess);
    const row = session.currentRow;

    track('guess_submitted', {
      turn: res.turn,
      word_length: game.word_length,
      latency_ms: Math.round(performance.now() - startedAt),
      greens: res.result.filter((m) => m === 'green').length,
    }, game.game_id);

    game.attempts_used = res.attempts_used;
    game.status = res.status;
    if (res.answer) game.answer = res.answer;
    if (res.answer_display) game.answer_display = res.answer_display;
    game.guesses.push({ guess: res.guess, turn: res.turn, result: res.result });

    session.currentRow += 1;
    session.currentGuess = '';
    renderStatus();

    await session.board.revealRow(row, letters, res.result);

    // Keyboard colours only after the board has revealed. Updating them
    // immediately spoiled every result about a second before the tiles showed
    // it, which is most of the game.
    session.keyboard.applyResult(letters, res.result);
    announce(session.board.describeRow(res.turn, letters, res.result));

    if (game.status !== 'active') {
      showResult();
    }
  } catch (err) {
    handleGuessError(err);
  } finally {
    session.busy = false;
    if (session.game.status === 'active') session.keyboard.setDisabled(false);
  }
}

function handleGuessError(err) {
  const game = session.game;
  if (!(err instanceof ApiError)) {
    toast(t('errors.generic'), { tone: 'error' });
    return;
  }

  switch (err.code) {
    case 'not_a_word': {
      session.board.shake();
      const suggestions = err.params.suggestions || [];
      const word = upper(err.params.word || session.currentGuess, game.language);
      const message = suggestions.length
        ? t('errors.not_a_word_suggest', {
            word,
            suggestions: suggestions.map((s) => upper(s, game.language)).join(', '),
          })
        : t('errors.not_a_word', { word, language: t(`languages.${game.language}`) });
      toast(message, { tone: 'error' });
      announce(message);
      track('guess_rejected', { reason: 'not_a_word', had_suggestions: suggestions.length > 0 },
        game.game_id);
      break;
    }
    case 'wrong_length':
      session.board.shake();
      toast(t('errors.wrong_length', err.params), { tone: 'error' });
      break;
    case 'game_not_found':
      State.clear('last_game_id');
      toast(t('errors.game_not_found'), { tone: 'error' });
      setTimeout(() => { window.location.href = '/'; }, 1200);
      break;
    case 'game_finished':
      toast(t('errors.game_finished'), { tone: 'error' });
      refreshGame();
      break;
    case 'offline':
    case 'timeout':
      toast(t(`errors.${err.code}`), { tone: 'error' });
      break;
    default:
      toast(t(`errors.${err.code}`) || t('errors.generic'), { tone: 'error' });
  }
}

/* --------------------------------------------------------------- drawer */

function setDrawerOpen(open) {
  dom.drawer.dataset.open = open ? 'true' : 'false';
  dom.drawerHandle.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function meaningTarget() {
  const game = session.game;
  if (game.status !== 'active') return game.answer;
  const last = game.guesses[game.guesses.length - 1];
  return last ? last.guess : null;
}

async function openMeaning(trigger = 'button') {
  const game = session.game;
  const word = meaningTarget();
  setDrawerOpen(true);

  if (!word) {
    dom.drawerBody.replaceChildren(emptyNote(t('game.meaningIntro')));
    return;
  }

  dom.drawerTitle.textContent =
    game.status === 'active' ? t('game.meaningOfGuess') : t('game.meaningOfAnswer');
  dom.drawerWord.textContent = upper(word, game.language);
  dom.drawerWord.lang = game.language;
  dom.drawerBody.replaceChildren(emptyNote(t('game.loading')));

  track('meaning_opened', { trigger, status: game.status }, game.game_id);

  try {
    const payload = await api.meaning(game.language, word, State.activeProfileId());
    renderMeaning(payload);
  } catch (err) {
    // textContent, not innerHTML. This line used to interpolate the server's
    // message straight into the DOM, and one of those messages echoed a URL
    // path segment back.
    dom.drawerBody.replaceChildren(emptyNote(t('errors.meaningFailed')));
  }
}

function emptyNote(text) {
  const node = document.createElement('p');
  node.className = 'drawer-empty';
  node.textContent = text;
  return node;
}

function renderMeaning(payload) {
  const fragment = document.createDocumentFragment();
  const entries = payload.entries || [];

  if (!entries.length && !Object.keys(payload.extras || {}).length) {
    fragment.appendChild(emptyNote(t('game.noDefinition')));
  }

  for (const entry of entries) {
    const block = document.createElement('div');
    block.className = 'definition';
    block.lang = payload.language;

    if (entry.part_of_speech) {
      const pos = document.createElement('span');
      pos.className = 'definition-pos';
      pos.textContent = entry.part_of_speech;
      block.appendChild(pos);
    }
    const def = document.createElement('p');
    def.textContent = entry.definition;
    block.appendChild(def);

    if (entry.example) {
      const example = document.createElement('p');
      example.className = 'definition-example';
      example.textContent = `“${entry.example}”`;
      block.appendChild(example);
    }
    if (entry.synonyms && entry.synonyms.length) {
      block.appendChild(listBlock(t('game.synonyms'), entry.synonyms));
    }
    fragment.appendChild(block);
  }

  const extras = payload.extras || {};
  if (extras.compounds && extras.compounds.length) {
    fragment.appendChild(listBlock(t('game.compounds'), extras.compounds));
  }
  if (extras.proverbs && extras.proverbs.length) {
    fragment.appendChild(listBlock(t('game.proverbs'), extras.proverbs));
  }
  if (extras.similar && extras.similar.length) {
    fragment.appendChild(listBlock(t('game.similar'), extras.similar));
  }

  if (payload.source_label) {
    const source = document.createElement('p');
    source.className = 'drawer-empty';
    source.textContent = `${t('game.source')}: ${payload.source_label}`;
    fragment.appendChild(source);
  }

  dom.drawerBody.replaceChildren(fragment);
}

function listBlock(label, items) {
  const wrap = document.createElement('div');
  wrap.className = 'definition';
  const heading = document.createElement('span');
  heading.className = 'definition-pos';
  heading.textContent = label;
  const body = document.createElement('p');
  body.textContent = items.join(', ');
  wrap.append(heading, body);
  return wrap;
}

/* ----------------------------------------------------------------- hint */

async function requestHint() {
  const game = session.game;
  if (game.status !== 'active') return;
  dom.hintBtn.disabled = true;
  setDrawerOpen(true);
  dom.drawerTitle.textContent = t('game.hint');
  dom.drawerBody.replaceChildren(emptyNote(t('game.loading')));

  try {
    const payload = await api.hint(game.game_id, 3);
    game.hints_used = payload.hints_used;

    const panel = document.createElement('div');
    panel.className = 'hint-panel';

    const intro = document.createElement('p');
    intro.className = 'drawer-empty';
    intro.textContent = t('game.hintIntro');
    panel.appendChild(intro);

    const count = document.createElement('p');
    count.className = 'drawer-empty';
    count.textContent = plural('game.hintCandidates', payload.candidates_remaining);
    panel.appendChild(count);

    // One candidate left means every guess scores 0 bits, because there is
    // nothing further to learn. Listing three suggestions at "0.00 bits" is
    // noise; say the useful thing instead.
    const solved = payload.candidates_remaining === 1;
    if (solved) {
      const note = document.createElement('p');
      note.className = 'drawer-empty';
      note.textContent = t('game.hintSolved');
      panel.appendChild(note);
    }

    for (const suggestion of solved
      ? payload.suggestions.filter((s) => s.is_candidate).slice(0, 1)
      : payload.suggestions) {
      const row = document.createElement('div');
      row.className = 'hint-row';
      const word = document.createElement('span');
      word.className = 'hint-word';
      word.lang = game.language;
      word.textContent = upper(suggestion.word, game.language);
      row.appendChild(word);
      if (!solved) {
        const bits = document.createElement('span');
        bits.className = 'hint-bits';
        bits.textContent = t('game.hintBits', { bits: suggestion.bits.toFixed(2) });
        row.appendChild(bits);
      }
      if (suggestion.is_candidate) {
        const flag = document.createElement('span');
        flag.className = 'chip';
        flag.textContent = t('game.hintCouldBeAnswer');
        row.appendChild(flag);
      }
      panel.appendChild(row);
    }

    dom.drawerBody.replaceChildren(panel);
    track('hint_used', {
      candidates_remaining: payload.candidates_remaining,
      source: payload.source,
      turn: game.attempts_used + 1,
    }, game.game_id);
  } catch (err) {
    const code = err instanceof ApiError ? err.code : 'generic';
    dom.drawerBody.replaceChildren(emptyNote(t(`errors.${code}`) || t('errors.generic')));
  } finally {
    dom.hintBtn.disabled = session.game.status !== 'active';
  }
}

/* ----------------------------------------------------------------- boot */

async function refreshGame() {
  session.game = await api.getGame(session.game.game_id);
  replayHistory();
  renderStatus();
  if (session.game.status !== 'active') showResult();
}

async function loadProfileChip(profileId) {
  if (!profileId) return;
  try {
    const profile = await api.getProfile(profileId);
    dom.profileName.textContent = profile.name;
    dom.avatar.innerHTML = '';
    dom.avatar.appendChild(renderAvatar(profile.avatar_config, profile.avatar_type));
    initTheme(profile.theme);
  } catch {
    // A stale profile id should not stop the game from being playable.
  }
}

function bindEvents() {
  document.addEventListener('keydown', (event) => {
    if (event.target instanceof HTMLInputElement) return;
    if (event.key === 'Escape') {
      setDrawerOpen(false);
      return;
    }
    const key = keyFromEvent(event, session.game.language);
    if (!key) return;
    event.preventDefault();
    if (key === 'ENTER') submitGuess();
    else if (key === 'BACK') popLetter();
    else {
      pushLetter(key);
      session.keyboard.flashLetter(key);
    }
  });

  dom.meaningBtn.addEventListener('click', () => openMeaning('button'));
  dom.hintBtn.addEventListener('click', requestHint);
  dom.drawerHandle.addEventListener('click', () => {
    setDrawerOpen(dom.drawer.dataset.open !== 'true');
  });
}

async function main() {
  const gameId = State.lastGameId();
  if (!gameId) {
    window.location.replace('/');
    return;
  }

  try {
    session.game = await api.getGame(gameId);
  } catch (err) {
    State.clear('last_game_id');
    window.location.replace('/');
    return;
  }

  initLocale(session.game.language);
  applyTranslations();
  await initFlags(State.activeProfileId());

  session.keyboard = new Keyboard(dom.keyboard, (key) => {
    if (key === 'ENTER') submitGuess();
    else if (key === 'BACK') popLetter();
    else pushLetter(key);
  });

  replayHistory();
  renderStatus();
  bindEvents();
  session.startedAt = Date.now();

  dom.hintBtn.hidden = getFlag('hint_affordance') === 'hidden';
  dom.drawerBody.replaceChildren(emptyNote(t('game.meaningIntro')));

  if (session.game.status !== 'active') {
    session.keyboard.setDisabled(true);
    showResult();
  }

  loadProfileChip(State.activeProfileId());
  track('game_opened', {
    language: session.game.language,
    word_length: session.game.word_length,
    difficulty: session.game.difficulty,
    resumed: session.game.guesses.length > 0,
  }, session.game.game_id);

  document.addEventListener('localechange', () => {
    applyTranslations();
    renderStatus();
  });
}

main();
