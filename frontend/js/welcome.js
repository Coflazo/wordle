/* Welcome screen controller. */

import { api, ApiError } from '/js/api.js';
import { State } from '/js/state.js';
import { toast } from '/js/toast.js';
import { registerServiceWorker, watchConnection } from '/js/offline.js';
import { mountAvatar, ACCESSORIES, AURA_COLORS, HAIR_STYLES, SHIRT_COLORS } from '/js/avatar.js';
import { initFlags, getFlag, track, flush } from '/js/analytics.js';
import { initTheme, setTheme, THEMES } from '/js/theme.js';
import { applyTranslations, initLocale, setLocale, t } from '/js/i18n.js';

const el = (id) => document.getElementById(id);

const dom = {
  languagePicker: el('language-picker'),
  difficultyPicker: el('difficulty-picker'),
  lengthPicker: el('length-picker'),
  themePicker: el('theme-picker'),
  characterRow: el('character-row'),
  editor: el('custom-editor'),
  nameInput: el('custom-name'),
  hairSelect: el('custom-hair'),
  accessorySelect: el('custom-accessory'),
  shirtRow: el('shirt-row'),
  auraRow: el('aura-row'),
  preview: el('avatar-preview'),
  previewSmall: el('avatar-preview-small'),
  startBtn: el('start-btn'),
  dailyBtn: el('daily-btn'),
  defaultAvatar: el('avatar-default'),
};

const setup = {
  language: State.sessionLanguage(),
  difficulty: State.sessionDifficulty(),
  length: State.sessionLength(),
  theme: null,
  characterMode: State.get('session_character_mode', 'default'),
  custom: State.get('session_custom_character', {
    name: '', hair: 'short_black', accessory: 'badge',
    shirt: SHIRT_COLORS[0], aura: AURA_COLORS[0],
  }),
};

/* ------------------------------------------------------- radio groups */

/**
 * Wire a group of buttons as a real radio group.
 * The markup previously declared role="tablist" with plain buttons inside —
 * invalid, since a tablist needs children with role="tab", and selection was
 * carried only by a CSS class. A screen reader announced "button EN, button
 * TR, button DE" with no indication of which was chosen.
 */
function bindRadioGroup(container, value, onChange) {
  const buttons = Array.from(container.querySelectorAll('button'));

  const select = (next, focus = false) => {
    for (const button of buttons) {
      const active = button.dataset.value === String(next);
      button.setAttribute('aria-checked', active ? 'true' : 'false');
      button.tabIndex = active ? 0 : -1;
      if (active && focus) button.focus();
    }
    onChange(next);
  };

  for (const button of buttons) {
    button.setAttribute('role', 'radio');
    button.type = 'button';
    button.addEventListener('click', () => select(button.dataset.value));
  }

  // Arrow-key roving focus, which is what makes a radio group usable without
  // a mouse.
  container.addEventListener('keydown', (event) => {
    const index = buttons.findIndex((b) => b === document.activeElement);
    if (index < 0) return;
    let next = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % buttons.length;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + buttons.length) % buttons.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = buttons.length - 1;
    if (next === null) return;
    event.preventDefault();
    select(buttons[next].dataset.value, true);
  });

  select(value);
  return select;
}

/* ----------------------------------------------------------- character */

function currentAvatarConfig() {
  if (setup.characterMode === 'default') {
    return { name: t('setup.defaultName') };
  }
  return { ...setup.custom, name: setup.custom.name || t('setup.customName') };
}

function renderPreview() {
  const config = { ...setup.custom, name: setup.custom.name || t('setup.customName') };
  mountAvatar(dom.preview, currentAvatarConfig(), setup.characterMode);
  // The tile in the character row always shows the custom build, so the choice
  // between "Oflaz" and "your own" is a visible comparison.
  mountAvatar(dom.previewSmall, config, 'custom');
}

function selectCharacter(mode) {
  setup.characterMode = mode;
  for (const tile of dom.characterRow.querySelectorAll('.character-tile')) {
    tile.setAttribute('aria-checked', tile.dataset.value === mode ? 'true' : 'false');
    tile.tabIndex = tile.dataset.value === mode ? 0 : -1;
  }
  dom.editor.open = mode === 'custom';
  renderPreview();
  State.set({ session_character_mode: mode });
  track('character_mode_changed', { mode });
}

function buildSwatches(container, colors, key, label) {
  container.replaceChildren();
  for (const color of colors) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'swatch';
    button.style.setProperty('--swatch-color', color);
    button.dataset.value = color;
    // These were eleven unlabelled buttons whose only content was an inline
    // background colour, announced as "button" eleven times.
    button.setAttribute('aria-label', `${label} ${color}`);
    button.setAttribute('aria-pressed', setup.custom[key] === color ? 'true' : 'false');
    button.addEventListener('click', () => {
      setup.custom[key] = color;
      for (const other of container.querySelectorAll('.swatch')) {
        other.setAttribute('aria-pressed', other.dataset.value === color ? 'true' : 'false');
      }
      persistCustom();
      renderPreview();
    });
    container.appendChild(button);
  }
}

function fillSelect(select, values, prefix) {
  select.replaceChildren();
  for (const value of values) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = t(`${prefix}.${value}`);
    select.appendChild(option);
  }
}

function persistCustom() {
  State.set({ session_custom_character: setup.custom });
}

/* --------------------------------------------------------------- start */

async function ensureProfile() {
  const existing = State.activeProfileId();
  if (existing) {
    try {
      await api.getProfile(existing);
      await api.updateProfile(existing, {
        avatar_type: setup.characterMode,
        avatar_config: currentAvatarConfig(),
        preferred_language: setup.language,
        theme: setup.theme,
      });
      return existing;
    } catch (err) {
      if (!(err instanceof ApiError) || err.code !== 'profile_not_found') throw err;
      State.clear('active_profile_id');
    }
  }

  const profile = await api.createProfile({
    name: currentAvatarConfig().name,
    avatar_type: setup.characterMode,
    avatar_config: currentAvatarConfig(),
    preferred_language: setup.language,
    theme: setup.theme,
  });
  State.set({ active_profile_id: profile.id });
  return profile.id;
}

async function startGame() {
  dom.startBtn.disabled = true;
  const original = dom.startBtn.textContent;
  dom.startBtn.textContent = t('setup.starting');

  try {
    const profileId = await ensureProfile();
    const payload = {
      profile_id: profileId,
      language: setup.language,
      difficulty: setup.difficulty,
    };
    if (setup.length) payload.word_length = Number(setup.length);

    const game = await api.startGame(payload);
    State.set({
      last_game_id: game.game_id,
      session_language: setup.language,
      session_difficulty: setup.difficulty,
      session_length: setup.length,
    });
    track('game_started', {
      language: setup.language,
      difficulty: setup.difficulty,
      requested_length: setup.length || 'mix',
      actual_length: game.word_length,
      character_mode: setup.characterMode,
    }, game.game_id);
    await flush();
    window.location.href = '/game';
  } catch (err) {
    const code = err instanceof ApiError ? err.code : 'generic';
    // Was `alert('Could not start the game: ' + e.message)` with the raw
    // backend string, in a modal that blocks the page.
    toast(`${t('errors.startFailed')} ${t(`errors.${code}`) || ''}`.trim(), { tone: 'error' });
    dom.startBtn.disabled = false;
    dom.startBtn.textContent = original;
  }
}

async function startDaily() {
  dom.dailyBtn.disabled = true;
  const original = dom.dailyBtn.textContent;
  dom.dailyBtn.textContent = t('setup.starting');
  try {
    const profileId = await ensureProfile();
    const payload = await api.daily(profileId, setup.language);
    State.set({ last_game_id: payload.game.game_id, session_language: setup.language });
    track('daily_started', { number: payload.number, language: setup.language,
                             resumed: payload.game.guesses.length > 0 }, payload.game.game_id);
    await flush();
    window.location.href = '/game';
  } catch (err) {
    const code = err instanceof ApiError ? err.code : 'generic';
    toast(`${t('errors.startFailed')} ${t(`errors.${code}`) || ''}`.trim(), { tone: 'error' });
    dom.dailyBtn.disabled = false;
    dom.dailyBtn.textContent = original;
  }
}

/* ------------------------------------------------------------------ boot */

function main() {
  initLocale(setup.language);
  setup.theme = initTheme(State.get('session_theme'));
  applyTranslations();

  bindRadioGroup(dom.languagePicker, setup.language, (value) => {
    setup.language = value;
    State.set({ session_language: value });
    // The interface follows the language being played, which is the whole
    // point — picking Turkish used to change only the word bank.
    setLocale(value);
    applyTranslations();
    refreshDynamicLabels();
    track('option_changed', { picker: 'language', value });
  });

  bindRadioGroup(dom.difficultyPicker, setup.difficulty, (value) => {
    setup.difficulty = value;
    State.set({ session_difficulty: value });
    track('option_changed', { picker: 'difficulty', value });
  });

  bindRadioGroup(dom.lengthPicker, setup.length || 'mix', (value) => {
    setup.length = value === 'mix' ? null : Number(value);
    State.set({ session_length: setup.length });
    track('option_changed', { picker: 'length', value });
  });

  bindRadioGroup(dom.themePicker, setup.theme, (value) => {
    setup.theme = setTheme(value);
    State.set({ session_theme: setup.theme });
    track('option_changed', { picker: 'theme', value });
  });

  for (const tile of dom.characterRow.querySelectorAll('.character-tile')) {
    tile.setAttribute('role', 'radio');
    tile.addEventListener('click', () => selectCharacter(tile.dataset.value));
    tile.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCharacter(tile.dataset.value);
      }
    });
  }

  fillSelect(dom.hairSelect, Object.keys(HAIR_STYLES), 'hair');
  fillSelect(dom.accessorySelect, ACCESSORIES, 'accessory');
  dom.hairSelect.value = setup.custom.hair;
  dom.accessorySelect.value = setup.custom.accessory;
  dom.nameInput.value = setup.custom.name || '';

  dom.hairSelect.addEventListener('change', () => {
    setup.custom.hair = dom.hairSelect.value;
    persistCustom();
    renderPreview();
  });
  dom.accessorySelect.addEventListener('change', () => {
    setup.custom.accessory = dom.accessorySelect.value;
    persistCustom();
    renderPreview();
  });
  dom.nameInput.addEventListener('input', () => {
    setup.custom.name = dom.nameInput.value.slice(0, 24);
    persistCustom();
    renderPreview();
  });

  buildSwatches(dom.shirtRow, SHIRT_COLORS, 'shirt', t('setup.shirt'));
  buildSwatches(dom.auraRow, AURA_COLORS, 'aura', t('setup.aura'));

  mountAvatar(dom.defaultAvatar, { name: t('setup.defaultName') }, 'default');
  selectCharacter(setup.characterMode);

  dom.startBtn.addEventListener('click', startGame);
  dom.dailyBtn.addEventListener('click', startDaily);

  initFlags(State.activeProfileId()).then(() => {
    if (getFlag('customize_open') === 'open') dom.editor.open = true;
    if (getFlag('default_length') === 'five' && setup.length === null) {
      // The server also enforces this; reflecting it here keeps the control
      // honest about what pressing Start will actually do.
      const five = dom.lengthPicker.querySelector('[data-value="5"]');
      if (five) five.click();
    }
    track('welcome_viewed', {});
  });

  dom.editor.addEventListener('toggle', () => {
    track('advanced_toggled', { open: dom.editor.open });
  });
}

function refreshDynamicLabels() {
  fillSelect(dom.hairSelect, Object.keys(HAIR_STYLES), 'hair');
  fillSelect(dom.accessorySelect, ACCESSORIES, 'accessory');
  dom.hairSelect.value = setup.custom.hair;
  dom.accessorySelect.value = setup.custom.accessory;
  buildSwatches(dom.shirtRow, SHIRT_COLORS, 'shirt', t('setup.shirt'));
  buildSwatches(dom.auraRow, AURA_COLORS, 'aura', t('setup.aura'));
  renderPreview();
}

main();

registerServiceWorker();
watchConnection();
