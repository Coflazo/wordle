/* Profile dashboard controller. */

import { api, ApiError } from '/js/api.js';
import { State } from '/js/state.js';
import { mountAvatar } from '/js/avatar.js';
import { toast } from '/js/toast.js';
import { registerServiceWorker, watchConnection } from '/js/offline.js';
import { initTheme } from '/js/theme.js';
import { prefersReducedMotion } from '/js/theme.js';
import {
  applyTranslations, formatDate, formatNumber, formatPercent, initLocale, plural, t, upper,
} from '/js/i18n.js';

const el = (id) => document.getElementById(id);

const dom = {
  avatar: el('profile-avatar'),
  name: el('profile-name'),
  meta: el('profile-meta'),
  tabs: el('lang-tabs'),
  empty: el('empty-state'),
  stats: el('stat-grid'),
  distribution: el('distribution'),
  languageSplit: el('language-split'),
  mastered: el('table-mastered'),
  known: el('table-known'),
  struggling: el('table-struggling'),
  timeline: el('timeline'),
  experiments: el('experiments'),
  sections: document.querySelectorAll('[data-section]'),
};

const view = {
  profileId: State.activeProfileId(),
  language: null,
  /** Cancels the previous dashboard fetch. Clicking tabs quickly used to fire
   *  overlapping requests with no sequencing, so the slower response won and
   *  the table could disagree with the highlighted tab. */
  inflight: null,
  countTimers: [],
};

/* -------------------------------------------------------------- helpers */

function clearCountTimers() {
  for (const id of view.countTimers) cancelAnimationFrame(id);
  view.countTimers = [];
}

/** Animate a number up. Bails to the final value under reduced motion. */
function countUp(node, target, format) {
  if (prefersReducedMotion()) {
    node.textContent = format(target);
    return;
  }
  const duration = 700;
  const start = performance.now();
  const tick = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    // easeOutCubic
    const eased = 1 - (1 - progress) ** 3;
    node.textContent = format(target * eased);
    if (progress < 1) view.countTimers.push(requestAnimationFrame(tick));
  };
  view.countTimers.push(requestAnimationFrame(tick));
}

function statCard({ value, label, sub, delta, deltaTone }) {
  const card = document.createElement('div');
  card.className = 'stat-card';

  const valueEl = document.createElement('div');
  valueEl.className = 'value';
  valueEl.textContent = '0';

  const labelEl = document.createElement('div');
  labelEl.className = 'label';
  labelEl.textContent = label;

  card.append(valueEl, labelEl);

  if (sub) {
    const subEl = document.createElement('div');
    subEl.className = 'sub';
    subEl.textContent = sub;
    card.appendChild(subEl);
  }
  if (delta) {
    const deltaEl = document.createElement('div');
    deltaEl.className = 'delta';
    if (deltaTone) deltaEl.dataset.tone = deltaTone;
    deltaEl.textContent = delta;
    card.appendChild(deltaEl);
  }
  return { card, valueEl, target: value };
}

function renderCore(core) {
  clearCountTimers();
  const int = (v) => formatNumber(Math.round(v));
  const pct = (v) => formatPercent(v, 0);
  const one = (v) => formatNumber(v, 1);

  let deltaText = t('profile.deltaUnknown');
  let deltaTone = null;
  if (core.delta_is_meaningful) {
    const magnitude = formatPercent(Math.abs(core.delta_last_7_games), 0);
    if (core.delta_last_7_games > 0.001) {
      deltaText = t('profile.deltaUp', { value: magnitude });
      deltaTone = 'up';
    } else if (core.delta_last_7_games < -0.001) {
      deltaText = t('profile.deltaDown', { value: magnitude });
      deltaTone = 'down';
    } else {
      deltaText = t('profile.deltaFlat');
    }
  }

  const cards = [
    statCard({ value: core.games_played, label: t('profile.gamesPlayed') }),
    statCard({ value: core.win_rate, label: t('profile.winRate'), delta: deltaText, deltaTone }),
    statCard({
      value: core.current_streak,
      label: t('profile.currentStreak'),
      sub: t('profile.currentStreakSub'),
    }),
    statCard({ value: core.best_streak, label: t('profile.bestStreak') }),
    statCard({
      value: core.avg_attempts,
      label: t('profile.avgAttempts'),
      sub: t('profile.avgAttemptsSub'),
    }),
    statCard({ value: core.longest_word_solved, label: t('profile.longestWord') }),
  ];

  const formats = [int, pct, int, int, one, int];
  dom.stats.replaceChildren(...cards.map((c) => c.card));
  cards.forEach((c, i) => countUp(c.valueEl, c.target, formats[i]));
}

function renderDistribution(distribution) {
  const fragment = document.createDocumentFragment();
  let any = false;

  for (const [length, buckets] of Object.entries(distribution)) {
    const total = Object.values(buckets).reduce((sum, n) => sum + n, 0);
    if (!total) continue;
    any = true;

    const group = document.createElement('div');
    group.className = 'dist-group';

    const label = document.createElement('div');
    label.className = 'dist-label';
    label.textContent = `${length} ${t('game.length').toLowerCase()}`;

    const bar = document.createElement('div');
    bar.className = 'dist-bar';
    bar.setAttribute('role', 'img');

    const parts = [];
    for (const [attempts, count] of Object.entries(buckets)) {
      if (!count) continue;
      const span = document.createElement('span');
      span.dataset.attempts = attempts;
      span.style.flexGrow = String(count);
      bar.appendChild(span);
      parts.push(`${count} in ${attempts}`);
    }
    // The data was previously only in a title attribute, invisible to touch
    // users and unreliable for assistive tech.
    bar.setAttribute('aria-label', `${length} letters: ${parts.join(', ')}`);

    group.append(label, bar);
    fragment.appendChild(group);
  }

  dom.distribution.replaceChildren(
    any ? fragment : emptyNote(t('profile.noEntries'))
  );
}

function renderLanguageSplit(rows) {
  if (!rows.length) {
    dom.languageSplit.replaceChildren(emptyNote(t('profile.noEntries')));
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    const item = document.createElement('div');
    item.className = 'arm-row';

    const name = document.createElement('span');
    name.className = 'arm-name';
    name.textContent = t(`languages.${row.language}`);

    const track = document.createElement('div');
    track.className = 'ci-track';
    const range = document.createElement('div');
    range.className = 'ci-range';
    range.style.left = '0';
    range.style.width = `${row.win_rate * 100}%`;
    track.appendChild(range);

    const figure = document.createElement('span');
    figure.className = 'arm-figure';
    figure.textContent = `${formatPercent(row.win_rate)} · ${plural('profile.games', row.games)}`;

    item.append(name, track, figure);
    fragment.appendChild(item);
  }
  dom.languageSplit.replaceChildren(fragment);
}

function renderWordTable(container, words, kind) {
  container.replaceChildren();
  if (!words.length) {
    container.appendChild(emptyNote(t('profile.noEntries')));
    return;
  }

  // A real table. These were nested divs with no headers and no table
  // semantics, so screen-reader table navigation did not work at all.
  const table = document.createElement('table');
  table.className = 'words';

  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of [t('profile.colWord'), t('profile.colLanguage'),
    kind === 'struggling' ? t('profile.colFails') : t('profile.colMastery')]) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = label;
    headRow.appendChild(th);
  }
  head.appendChild(headRow);

  const body = document.createElement('tbody');
  for (const word of words) {
    const row = document.createElement('tr');

    const wordCell = document.createElement('td');
    wordCell.className = 'word';
    wordCell.lang = word.language;
    wordCell.textContent = upper(word.display || word.word, word.language);

    const langCell = document.createElement('td');
    langCell.textContent = word.language.toUpperCase();

    const figureCell = document.createElement('td');
    figureCell.className = 'num';
    figureCell.textContent = kind === 'struggling'
      ? formatNumber(word.failed)
      : formatPercent(word.mastery);

    row.append(wordCell, langCell, figureCell);
    body.appendChild(row);
  }

  table.append(head, body);
  const scroller = document.createElement('div');
  scroller.className = 'word-rows';
  scroller.appendChild(table);
  container.appendChild(scroller);
}

function renderTimeline(rows) {
  if (!rows.length) {
    dom.timeline.replaceChildren(emptyNote(t('profile.noGames')));
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    const item = document.createElement('div');
    item.className = 'tl-row';

    const date = document.createElement('span');
    date.textContent = formatDate(row.finished_at);

    const lang = document.createElement('span');
    lang.className = 'chip';
    lang.textContent = row.language.toUpperCase();

    const word = document.createElement('span');
    word.className = 'word';
    word.lang = row.language;
    word.textContent = upper(row.answer_display || row.answer, row.language);

    const attempts = document.createElement('span');
    attempts.className = 'attempts';
    attempts.textContent = row.resigned
      ? t('profile.resigned')
      : `${row.attempts_used}/${row.attempts_allowed}`;

    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.dataset.outcome = row.status;
    // The outcome was a bare coloured dot with no text equivalent.
    dot.setAttribute('role', 'img');
    dot.setAttribute('aria-label', row.status === 'won' ? t('game.won') : t('game.lost'));

    item.append(date, lang, word, attempts, dot);
    fragment.appendChild(item);
  }
  dom.timeline.replaceChildren(fragment);
}

function renderExperiments(experiments) {
  const fragment = document.createDocumentFragment();

  const intro = document.createElement('p');
  intro.className = 'sub';
  intro.textContent = t('profile.experimentsIntro');
  fragment.appendChild(intro);

  for (const experiment of experiments) {
    const card = document.createElement('div');
    card.className = 'card experiment';

    const title = document.createElement('h4');
    title.textContent = experiment.experiment;

    const desc = document.createElement('p');
    desc.className = 'desc';
    desc.textContent = experiment.description;

    card.append(title, desc);

    for (const arm of experiment.arms) {
      const row = document.createElement('div');
      row.className = 'arm-row';

      const name = document.createElement('span');
      name.className = 'arm-name';
      name.textContent = arm.arm;

      const track = document.createElement('div');
      track.className = 'ci-track';
      const range = document.createElement('div');
      range.className = 'ci-range';
      range.style.left = `${arm.ci_low * 100}%`;
      range.style.width = `${Math.max(1, (arm.ci_high - arm.ci_low) * 100)}%`;
      const point = document.createElement('div');
      point.className = 'ci-point';
      point.style.left = `${arm.win_rate * 100}%`;
      track.append(range, point);
      track.setAttribute('role', 'img');
      track.setAttribute(
        'aria-label',
        `${arm.arm}: ${formatPercent(arm.win_rate)} (${formatPercent(arm.ci_low)}–${formatPercent(arm.ci_high)})`
      );

      const figure = document.createElement('span');
      figure.className = 'arm-figure';
      figure.textContent = `${formatPercent(arm.win_rate)} · n=${arm.games}`;

      row.append(name, track, figure);
      card.appendChild(row);
    }
    fragment.appendChild(card);
  }
  dom.experiments.replaceChildren(fragment);
}

function emptyNote(text) {
  const node = document.createElement('p');
  node.className = 'empty-state';
  node.textContent = text;
  return node;
}

function setSectionsVisible(visible) {
  for (const section of dom.sections) section.hidden = !visible;
  dom.empty.hidden = visible;
}

function showSkeleton() {
  const cards = Array.from({ length: 6 }, () => {
    const card = document.createElement('div');
    card.className = 'stat-card';
    const value = document.createElement('div');
    value.className = 'value skeleton';
    value.textContent = '00';
    const label = document.createElement('div');
    label.className = 'label skeleton';
    label.textContent = '     ';
    card.append(value, label);
    return card;
  });
  dom.stats.replaceChildren(...cards);
}

/* ---------------------------------------------------------------- load */

async function refresh() {
  if (!view.profileId) {
    setSectionsVisible(false);
    dom.empty.replaceChildren(emptyNote(t('errors.profile_not_found')));
    return;
  }

  if (view.inflight) view.inflight.abort();
  const controller = new AbortController();
  view.inflight = controller;

  showSkeleton();
  try {
    const data = await api.dashboard(view.profileId, view.language, { signal: controller.signal });
    if (controller.signal.aborted) return;

    dom.name.textContent = data.profile.name;
    dom.meta.textContent = [
      t('profile.prefers', { language: t(`languages.${data.profile.preferred_language}`) }),
      data.profile.created_at ? t('profile.since', { date: formatDate(data.profile.created_at) }) : null,
    ].filter(Boolean).join(' · ');

    const hasGames = data.core.games_played > 0;
    setSectionsVisible(hasGames);
    if (!hasGames) {
      dom.empty.replaceChildren(emptyNote(t('profile.noGames')));
      return;
    }

    renderCore(data.core);
    renderDistribution(data.attempts_distribution);
    renderLanguageSplit(data.language_split);
    renderWordTable(dom.mastered, data.vocabulary.mastered, 'mastered');
    renderWordTable(dom.known, data.vocabulary.known, 'known');
    renderWordTable(dom.struggling, data.vocabulary.struggling, 'struggling');
    renderTimeline(data.timeline);
  } catch (err) {
    if (controller.signal.aborted) return;
    // Previously this returned early with the shimmer still running, so a
    // failed fetch looked like a permanent loading state.
    setSectionsVisible(false);
    dom.empty.replaceChildren(emptyNote(t('errors.dashboardFailed')));
    const code = err instanceof ApiError ? err.code : 'generic';
    toast(t(`errors.${code}`) || t('errors.dashboardFailed'), { tone: 'error' });
  } finally {
    if (view.inflight === controller) view.inflight = null;
  }
}

async function loadExperiments() {
  try {
    const payload = await api.experiments();
    renderExperiments(payload.experiments);
  } catch {
    dom.experiments.replaceChildren(emptyNote(t('profile.noEntries')));
  }
}

function bindTabs() {
  const buttons = Array.from(dom.tabs.querySelectorAll('button'));
  const select = (value) => {
    view.language = value === 'all' ? null : value;
    for (const button of buttons) {
      button.setAttribute('aria-selected', button.dataset.value === value ? 'true' : 'false');
      button.tabIndex = button.dataset.value === value ? 0 : -1;
    }
    refresh();
  };
  for (const button of buttons) {
    button.setAttribute('role', 'tab');
    button.addEventListener('click', () => select(button.dataset.value));
  }
  dom.tabs.setAttribute('role', 'tablist');
  select('all');
}

async function main() {
  const profile = view.profileId ? await api.getProfile(view.profileId).catch(() => null) : null;
  initLocale(profile ? profile.preferred_language : null);
  initTheme(profile ? profile.theme : null);
  applyTranslations();

  if (profile) {
    mountAvatar(dom.avatar, profile.avatar_config, profile.avatar_type);
  }

  bindTabs();
  loadExperiments();

  document.addEventListener('localechange', () => {
    applyTranslations();
    refresh();
  });
}

main();

registerServiceWorker();
watchConnection();
