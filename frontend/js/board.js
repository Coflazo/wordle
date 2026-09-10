/* The guess grid.
 *
 * Tiles are held in a 2D array built once. The previous version ran a
 * `querySelector` with an attribute selector per tile per keystroke — ten
 * document queries for every letter typed on a ten-wide board, and up to
 * ninety when replaying a finished game at page load.
 *
 * The grid also carries real semantics now. It used to be bare <div>s whose
 * only signal was background-color: nothing was announced, and the correct and
 * present colours measure 1.33:1 against each other, so the result was
 * unreadable with deuteranopia and invisible to a screen reader.
 */

import { t, upper } from '/js/i18n.js';
import { prefersReducedMotion } from '/js/theme.js';

const STATE_NAMES = { correct: 'markCorrect', present: 'markPresent', absent: 'markAbsent' };

export class Board {
  constructor(root) {
    this.root = root;
    this.tiles = [];
    this.cols = 5;
    this.rows = 6;
    this.timers = [];
    this.locale = 'en';
  }

  build(cols, rows, locale = 'en') {
    this.clearTimers();
    this.cols = cols;
    this.rows = rows;
    this.locale = locale;
    this.tiles = [];

    this.root.style.setProperty('--cols', String(cols));
    this.root.style.setProperty('--rows', String(rows));
    this.root.setAttribute('role', 'grid');
    this.root.setAttribute('aria-readonly', 'true');
    this.root.setAttribute('aria-label', t('game.boardLabel', { rows, cols }));

    // One fragment, one insertion. The old build appended up to 100 nodes into
    // the live DOM one at a time.
    const fragment = document.createDocumentFragment();
    for (let r = 0; r < rows; r += 1) {
      const row = document.createElement('div');
      row.className = 'board-row';
      row.setAttribute('role', 'row');
      row.style.display = 'contents';
      const rowTiles = [];
      for (let c = 0; c < cols; c += 1) {
        const tile = document.createElement('div');
        tile.className = 'tile';
        tile.setAttribute('role', 'gridcell');
        tile.setAttribute('aria-label', t('game.tileEmpty'));
        row.appendChild(tile);
        rowTiles.push(tile);
      }
      this.tiles.push(rowTiles);
      fragment.appendChild(row);
    }
    this.root.replaceChildren(fragment);
  }

  clearTimers() {
    for (const id of this.timers) clearTimeout(id);
    this.timers = [];
  }

  later(fn, delay) {
    const id = setTimeout(fn, delay);
    this.timers.push(id);
    return id;
  }

  setTypedRow(row, letters) {
    const rowTiles = this.tiles[row];
    if (!rowTiles) return;
    for (let c = 0; c < this.cols; c += 1) {
      const tile = rowTiles[c];
      const ch = letters[c] || '';
      const shown = ch ? upper(ch, this.locale) : '';
      if (tile.textContent !== shown) {
        tile.textContent = shown;
        tile.dataset.filled = ch ? 'true' : 'false';
        tile.setAttribute('aria-label', ch ? shown : t('game.tileEmpty'));
      }
    }
  }

  /**
   * Flip a row, one tile at a time. Resolves when the last tile has settled,
   * so the caller can hold the input lock and delay the result banner until
   * the board has actually finished — the old code used a flat 800ms, which on
   * a ten-letter win announced the answer while four tiles were still blank.
   */
  revealRow(row, letters, marks) {
    const rowTiles = this.tiles[row];
    if (!rowTiles) return Promise.resolve();

    const reduced = prefersReducedMotion();
    const stagger = reduced ? 0 : this.readMs('--reveal-stagger', 90);
    const flip = reduced ? 0 : this.readMs('--dur-reveal', 420);

    return new Promise((resolve) => {
      for (let c = 0; c < letters.length; c += 1) {
        const tile = rowTiles[c];
        if (!tile) continue;
        const letter = upper(letters[c], this.locale);
        const mark = marks[c];

        this.later(() => {
          tile.textContent = letter;
          tile.dataset.filled = 'true';
          if (!reduced) tile.classList.add('is-revealing');
          // Swap the colour at the midpoint of the flip, so the tile turns
          // while it is edge-on rather than in full view.
          this.later(() => {
            tile.dataset.state = mark === 'green' ? 'correct' : mark === 'yellow' ? 'present' : 'absent';
            tile.setAttribute(
              'aria-label',
              t(`game.${STATE_NAMES[tile.dataset.state]}`, { letter })
            );
          }, flip / 2);
          this.later(() => tile.classList.remove('is-revealing'), flip);
        }, c * stagger);
      }
      this.later(resolve, Math.max(0, (letters.length - 1) * stagger + flip));
    });
  }

  readMs(name, fallback) {
    const raw = getComputedStyle(this.root).getPropertyValue(name).trim();
    const value = parseFloat(raw);
    return Number.isFinite(value) ? (raw.endsWith('ms') ? value : value * 1000) : fallback;
  }

  /** A sentence describing a scored row, for the live region. */
  describeRow(rowNumber, letters, marks) {
    const detail = letters
      .map((ch, i) => {
        const mark = marks[i];
        const state = mark === 'green' ? 'correct' : mark === 'yellow' ? 'present' : 'absent';
        return t(`game.${STATE_NAMES[state]}`, { letter: upper(ch, this.locale) });
      })
      .join(', ');
    return t('game.guessResult', {
      row: rowNumber,
      word: upper(letters.join(''), this.locale),
      detail,
    });
  }

  shake() {
    if (prefersReducedMotion()) return;
    this.root.classList.remove('is-invalid');
    // Reading offsetWidth forces the style recalc that restarts the animation.
    void this.root.offsetWidth;
    this.root.classList.add('is-invalid');
    this.later(() => this.root.classList.remove('is-invalid'), 500);
  }
}
