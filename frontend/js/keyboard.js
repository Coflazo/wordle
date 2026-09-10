/* On-screen keyboard.
 *
 * Layouts are per language. Sizing is entirely CSS — keys flex from a zero
 * basis so a row always divides the width it is given. The old sheet floored
 * keys at 36px with no wrap, which meant the Turkish bottom row needed 544px
 * and simply ran off both edges of a phone, taking the Enter key with it. On a
 * touch device with no physical Enter there was then no way to submit at all.
 */

import { t, upper } from '/js/i18n.js';

export const LAYOUTS = {
  en: [
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    ['ENTER', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'BACK'],
  ],
  tr: [
    ['e', 'r', 't', 'y', 'u', 'ı', 'o', 'p', 'ğ', 'ü'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ş', 'i'],
    ['ENTER', 'z', 'c', 'v', 'b', 'n', 'm', 'ö', 'ç', 'BACK'],
  ],
  de: [
    ['q', 'w', 'e', 'r', 't', 'z', 'u', 'i', 'o', 'p', 'ü'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ö', 'ä'],
    ['ENTER', 'y', 'x', 'c', 'v', 'b', 'n', 'm', 'ß', 'BACK'],
  ],
};

const PRIORITY = { absent: 1, present: 2, correct: 3 };

export class Keyboard {
  constructor(root, onKey) {
    this.root = root;
    this.onKey = onKey;
    this.keys = new Map();
    this.locale = 'en';
    this.disabled = false;

    // One delegated listener instead of one per key. The old code bound a
    // listener per button inside a function that began by clearing innerHTML,
    // which leaks on every rebuild.
    // pointerdown, not click: click adds 50-300ms of perceived latency on
    // touch, and a tapped button keeps DOM focus so a later Space press
    // re-fires it — which used to retype the last letter.
    this.root.addEventListener('pointerdown', (event) => {
      const button = event.target.closest('.kb-key');
      if (!button || this.disabled) return;
      event.preventDefault();
      this.flash(button);
      this.onKey(button.dataset.key);
    });
  }

  build(language) {
    this.locale = language;
    this.keys.clear();
    const layout = LAYOUTS[language] || LAYOUTS.en;
    // Announce Turkish and German keys in their own language rather than
    // letting a screen reader read them with an English voice.
    this.root.setAttribute('lang', language);
    this.root.setAttribute('role', 'group');
    this.root.setAttribute('aria-label', t('setup.language'));

    const fragment = document.createDocumentFragment();
    for (const row of layout) {
      const rowEl = document.createElement('div');
      rowEl.className = 'kb-row';
      for (const key of row) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'kb-key';
        button.dataset.key = key;
        if (key === 'ENTER' || key === 'BACK') {
          button.dataset.wide = 'true';
          button.textContent = key === 'ENTER' ? t('game.enter') : '⌫';
          // The backspace glyph had no accessible name at all.
          button.setAttribute('aria-label', key === 'ENTER' ? t('game.enter') : t('game.backspace'));
        } else {
          button.textContent = upper(key, language);
          button.setAttribute('aria-label', upper(key, language));
        }
        rowEl.appendChild(button);
        this.keys.set(key, button);
      }
      fragment.appendChild(rowEl);
    }
    this.root.replaceChildren(fragment);
  }

  /** Merge letter states, keeping the strongest result seen for each letter. */
  applyResult(letters, marks) {
    for (let i = 0; i < letters.length; i += 1) {
      const button = this.keys.get(letters[i]);
      if (!button) continue;
      const next = marks[i] === 'green' ? 'correct' : marks[i] === 'yellow' ? 'present' : 'absent';
      const current = button.dataset.state;
      if (!current || PRIORITY[next] > PRIORITY[current]) {
        button.dataset.state = next;
      }
    }
  }

  flash(button) {
    button.classList.remove('is-pressed');
    void button.offsetWidth;
    button.classList.add('is-pressed');
    setTimeout(() => button.classList.remove('is-pressed'), 200);
  }

  flashLetter(letter) {
    const button = this.keys.get(letter);
    if (button) this.flash(button);
  }

  /** Lock every key. Keys used to stay live after the game ended and during
   *  the reveal, silently doing nothing with no visual feedback at all. */
  setDisabled(disabled) {
    this.disabled = disabled;
    for (const button of this.keys.values()) {
      button.disabled = disabled;
    }
  }

  reset() {
    for (const button of this.keys.values()) delete button.dataset.state;
  }
}

/**
 * Map a physical keypress to a game letter.
 * Returns 'ENTER', 'BACK', a single letter, or null.
 */
export function keyFromEvent(event, language) {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;
  if (event.key === 'Enter') return 'ENTER';
  if (event.key === 'Backspace') return 'BACK';
  if (event.key.length !== 1) return null;

  let ch;
  if (language === 'tr') {
    // Turkish casing is not the invariant mapping: 'I' lowercases to 'ı' and
    // 'İ' to 'i'. The old regex also omitted uppercase Ç, Ğ and Ş entirely, so
    // three of the six Turkish letters were silently dropped with Caps Lock on.
    if (event.key === 'İ') ch = 'i';
    else if (event.key === 'I') ch = 'ı';
    else ch = event.key.toLocaleLowerCase('tr-TR');
  } else {
    ch = event.key.toLocaleLowerCase(language === 'de' ? 'de-DE' : 'en-US');
  }

  const layout = LAYOUTS[language] || LAYOUTS.en;
  return layout.some((row) => row.includes(ch)) ? ch : null;
}
