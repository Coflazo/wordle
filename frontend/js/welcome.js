// Welcome page controller: language + difficulty + character picker + Start Game.

import { api } from '/js/api.js';
import { State } from '/js/state.js';
import { mountAvatars, setAvatar } from '/js/avatar.js';

const DEFAULT_CHARACTER = {
  name: 'Oflaz',
  base: 'pixel-human',
  hair: 'short-black',
  accessory: 'badge-o',
  shirt: 'midnight',
  aura: 'green-glow',
};

const state = {
  language: State.sessionLanguage(),
  difficulty: State.sessionDifficulty(),
  wordLength: State.get().session_word_length || 'random',
  characterMode: State.get().session_character_mode || 'default',
  customCharacter:
    State.get().session_custom_character || {
      name: 'You',
      base: 'pixel-human',
      hair: 'short-brown',
      accessory: 'glasses',
      shirt: 'cyan',
      aura: 'cyan-glow',
    },
};

function setSegmented(container, value) {
  container.querySelectorAll('button').forEach((b) => {
    b.classList.toggle('is-active', b.dataset.value === value);
  });
}

function setCharacterTile(mode) {
  document.querySelectorAll('.character-tile').forEach((t) => {
    t.classList.toggle('is-active', t.dataset.character === mode);
  });
  const editor = document.getElementById('custom-editor');
  editor.classList.toggle('hidden', mode !== 'custom');
}

function refreshEditorPreview() {
  const el = document.getElementById('editor-preview');
  if (el) setAvatar(el, state.customCharacter);
  const tile = document.getElementById('custom-avatar-preview');
  if (tile) setAvatar(tile, state.customCharacter);
}

function bindSegmented(id, key) {
  const el = document.getElementById(id);
  setSegmented(el, state[key]);
  el.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-value]');
    if (!btn) return;
    state[key] = btn.dataset.value;
    setSegmented(el, state[key]);
  });
}

function bindCharacterTiles() {
  document.querySelectorAll('.character-tile').forEach((t) => {
    t.addEventListener('click', () => {
      state.characterMode = t.dataset.character;
      setCharacterTile(state.characterMode);
    });
    t.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); t.click(); }
    });
  });
  setCharacterTile(state.characterMode);
}

function bindEditor() {
  const nameInput = document.getElementById('custom-name');
  nameInput.value = state.customCharacter.name || '';
  nameInput.addEventListener('input', () => {
    state.customCharacter.name = nameInput.value.trim() || 'You';
    refreshEditorPreview();
  });

  const hair = document.getElementById('custom-hair');
  hair.value = state.customCharacter.hair;
  hair.addEventListener('change', () => {
    state.customCharacter.hair = hair.value;
    refreshEditorPreview();
  });

  const acc = document.getElementById('custom-accessory');
  acc.value = state.customCharacter.accessory;
  acc.addEventListener('change', () => {
    state.customCharacter.accessory = acc.value;
    refreshEditorPreview();
  });

  document.querySelectorAll('#custom-shirt .swatch').forEach((s) => {
    s.classList.toggle('is-active', s.dataset.shirt === state.customCharacter.shirt);
    s.addEventListener('click', () => {
      document.querySelectorAll('#custom-shirt .swatch').forEach((x) => x.classList.remove('is-active'));
      s.classList.add('is-active');
      state.customCharacter.shirt = s.dataset.shirt;
      refreshEditorPreview();
    });
  });

  document.querySelectorAll('#custom-aura .swatch').forEach((s) => {
    s.classList.toggle('is-active', s.dataset.aura === state.customCharacter.aura);
    s.addEventListener('click', () => {
      document.querySelectorAll('#custom-aura .swatch').forEach((x) => x.classList.remove('is-active'));
      s.classList.add('is-active');
      state.customCharacter.aura = s.dataset.aura;
      refreshEditorPreview();
    });
  });
}

async function ensureProfile() {
  const activeId = State.activeProfileId();
  const isCustom = state.characterMode === 'custom';
  const character = isCustom ? state.customCharacter : DEFAULT_CHARACTER;
  const name = character.name || (isCustom ? 'You' : 'Oflaz');

  // If we already have this profile matching the character type + name, reuse it.
  if (activeId) {
    try {
      const existing = await api.getProfile(activeId);
      if (existing) {
        await api.updateProfile(activeId, {
          name,
          avatar_type: isCustom ? 'custom' : 'default',
          avatar_config: character,
          preferred_language: state.language,
        });
        return existing.id;
      }
    } catch (_) {
      // fall through to create
    }
  }

  const created = await api.createProfile({
    name,
    avatar_type: isCustom ? 'custom' : 'default',
    avatar_config: character,
    preferred_language: state.language,
  });
  State.setActiveProfileId(created.id);
  return created.id;
}

async function startGame() {
  const btn = document.getElementById('start-btn');
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = 'Loading …';
  try {
    const profileId = await ensureProfile();
    State.set({
      session_language: state.language,
      session_difficulty: state.difficulty,
      session_word_length: state.wordLength,
      session_character_mode: state.characterMode,
      session_custom_character: state.customCharacter,
    });
    const gameRequest = {
      profile_id: profileId,
      language: state.language,
      difficulty: state.difficulty,
    };
    if (state.wordLength !== 'random') {
      gameRequest.word_length = Number(state.wordLength);
    }
    const game = await api.startGame(gameRequest);
    State.set({ last_game_id: game.game_id });
    window.location.href = '/game';
  } catch (e) {
    console.error(e);
    alert('Could not start the game: ' + e.message);
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

function resetStartButton() {
  const btn = document.getElementById('start-btn');
  if (!btn) return;
  btn.disabled = false;
  btn.textContent = 'Start Game';
}

document.addEventListener('DOMContentLoaded', () => {
  mountAvatars();
  bindSegmented('language-picker', 'language');
  bindSegmented('difficulty-picker', 'difficulty');
  bindSegmented('length-picker', 'wordLength');
  bindCharacterTiles();
  bindEditor();
  refreshEditorPreview();
  document.getElementById('start-btn').addEventListener('click', startGame);
});

// If the browser restored this page from the bfcache (e.g. after the game page
// redirected home), the button might still say "Loading …". Reset it.
window.addEventListener('pageshow', resetStartButton);
