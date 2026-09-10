// Profile dashboard: fetches stats and renders cards, distribution, tables, timeline.

import { api } from '/js/api.js';
import { State } from '/js/state.js';
import { setAvatar } from '/js/avatar.js';

const state = { profile: null, language: null, dashboard: null };

const $ = (sel) => document.querySelector(sel);

function fmtPercent(n) {
  return `${Math.round((n || 0) * 100)}%`;
}

function countUp(el, target, isPercent = false) {
  const start = performance.now();
  const duration = 900;
  const from = 0;
  const to = target;
  function tick(t) {
    const p = Math.min(1, (t - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    const v = from + (to - from) * eased;
    el.textContent = isPercent ? fmtPercent(v) : Math.round(v).toString();
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function renderCore(core) {
  countUp($('[data-metric="games_played"]'), core.games_played);
  countUp($('[data-metric="win_rate"]'), core.win_rate, true);
  countUp($('[data-metric="current_streak"]'), core.current_streak);
  countUp($('[data-metric="best_streak"]'), core.best_streak);
  const avg = Number(core.avg_guesses_per_win || 0).toFixed(1);
  $('[data-metric="avg_guesses"]').textContent = avg;
  const ring = $('#win-rate-ring');
  const pct = Math.round((core.win_rate || 0) * 100);
  ring.style.setProperty('--pct', pct);
  ring.querySelector('.ring-value').textContent = `${pct}%`;
}

function renderVocab(vocab) {
  $('[data-metric="mastered"]').textContent = vocab.mastered_count;
}

function renderDistribution(dist) {
  const grid = $('#dist-grid');
  grid.innerHTML = '';
  const lengths = Object.keys(dist).sort((a, b) => Number(a) - Number(b));
  for (const l of lengths) {
    const buckets = dist[l];
    const total = Object.values(buckets).reduce((a, b) => a + b, 0);
    const label = document.createElement('div');
    label.className = 'dist-len';
    label.textContent = `${l} letters`;
    grid.appendChild(label);
    const bar = document.createElement('div');
    bar.className = 'dist-bar';
    if (total > 0) {
      for (const k of Object.keys(buckets).sort((a, b) => Number(a) - Number(b))) {
        const c = buckets[k];
        if (c <= 0) continue;
        const span = document.createElement('span');
        span.className = `k${k}`;
        span.style.width = `${(c / total) * 100}%`;
        span.title = `solved in ${k} attempt(s): ${c}`;
        bar.appendChild(span);
      }
    }
    grid.appendChild(bar);
    const count = document.createElement('div');
    count.className = 'dist-count';
    count.textContent = String(total);
    grid.appendChild(count);
  }
}

function renderLanguageSplit(split) {
  const root = $('#language-split');
  root.innerHTML = '';
  const total = Object.values(split).reduce((a, b) => a + b, 0) || 1;
  const langs = [
    { key: 'en', label: 'English' },
    { key: 'tr', label: 'Turkish' },
    { key: 'de', label: 'German' },
  ];
  for (const lang of langs) {
    const c = split[lang.key] || 0;
    const card = document.createElement('div');
    card.className = `lang-card ${lang.key}`;
    card.innerHTML = `
      <div class="row"><b>${lang.label}</b><div class="spacer"></div><span class="mono small muted">${c} games</span></div>
      <div class="bar"><span style="width:${(c / total) * 100}%"></span></div>
    `;
    root.appendChild(card);
  }
}

function renderWordTable(root, words, kind) {
  root.innerHTML = '';
  if (!words.length) {
    root.innerHTML = '<div class="muted small mono">No entries yet.</div>';
    return;
  }
  for (const w of words) {
    const row = document.createElement('div');
    row.className = 'word-row';
    const mastery = Math.round((w.mastery_score || 0) * 100);
    row.innerHTML = `
      <span class="w">${w.word}</span>
      <span class="lang">${w.language}</span>
      ${kind === 'struggling'
        ? `<span class="fails">${w.failed} ✗</span>`
        : `<span class="m">${mastery}%</span>`}
    `;
    root.appendChild(row);
  }
}

function renderTimeline(items) {
  const root = $('#timeline');
  root.innerHTML = '';
  if (!items.length) {
    root.innerHTML = '<div class="muted small mono">No completed games yet.</div>';
    return;
  }
  for (const it of items) {
    const row = document.createElement('div');
    row.className = 'tl-row';
    const finished = it.finished_at ? new Date(it.finished_at) : null;
    const date = finished ? finished.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—';
    row.innerHTML = `
      <span class="date">${date}</span>
      <span class="lang chip chip-${it.language}">${it.language}</span>
      <span class="word">${it.answer || '—'}</span>
      <span class="attempts">${it.attempts_used}/${it.attempts_allowed}</span>
      <span class="dot ${it.status === 'won' ? 'win' : 'lose'}"></span>
    `;
    root.appendChild(row);
  }
}

async function ensureProfile() {
  const id = State.activeProfileId();
  if (id) {
    try {
      return await api.getProfile(id);
    } catch (_) {}
  }
  const list = await api.listProfiles();
  if (list.length) return list[0];
  return null;
}

function showSkeleton() {
  document.querySelectorAll('.stat-card .value').forEach((el) => {
    el.textContent = ' ';
    el.classList.add('skeleton');
  });
}
function hideSkeleton() {
  document.querySelectorAll('.stat-card .value').forEach((el) => {
    el.classList.remove('skeleton');
  });
}

// Small crossfade when re-rendering the dashboard for a language tab change.
function fadeReplace(el, updateFn) {
  el.style.transition = 'opacity 180ms cubic-bezier(0.16, 1, 0.3, 1)';
  el.style.opacity = '0';
  setTimeout(() => {
    updateFn();
    el.style.opacity = '1';
  }, 160);
}

async function refresh({ soft = false } = {}) {
  if (!soft) showSkeleton();
  let dash;
  try {
    dash = await api.dashboard(state.profile.id, state.language || undefined);
  } catch (e) {
    console.error('dashboard failed', e);
    return;
  }
  state.dashboard = dash;

  if (!dash.core.games_played) {
    $('#empty-state').classList.remove('hidden');
    $('#dashboard').classList.add('hidden');
    hideSkeleton();
    return;
  }
  $('#empty-state').classList.add('hidden');
  $('#dashboard').classList.remove('hidden');

  hideSkeleton();

  const paint = () => {
    renderCore(dash.core);
    renderVocab(dash.vocab);
    renderDistribution(dash.attempts_distribution);
    renderLanguageSplit(dash.language_split);
    renderWordTable($('#tbl-mastered'), dash.mastered_words, 'mastered');
    renderWordTable($('#tbl-known'), dash.known_words, 'known');
    renderWordTable($('#tbl-struggling'), dash.struggling_words, 'struggling');
    renderTimeline(dash.timeline);
  };
  if (soft) fadeReplace($('#dashboard'), paint);
  else paint();
}

function bindTabs() {
  document.querySelectorAll('#lang-tabs button').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('is-active')) return;
      document.querySelectorAll('#lang-tabs button').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      state.language = btn.dataset.lang || null;
      refresh({ soft: true });
    });
  });
}

async function init() {
  const p = await ensureProfile();
  if (!p) {
    $('#empty-state').classList.remove('hidden');
    $('#dashboard').classList.add('hidden');
    $('#profile-name').textContent = 'No profile yet';
    return;
  }
  State.setActiveProfileId(p.id);
  state.profile = p;
  $('#profile-name').textContent = p.name;
  $('#profile-lang').textContent = `preferred: ${p.preferred_language}`;
  const since = new Date(p.created_at);
  $('#profile-since').textContent = `since ${since.toLocaleDateString()}`;
  setAvatar($('#profile-avatar'), p.avatar_config);
  bindTabs();
  await refresh();
}

init();
