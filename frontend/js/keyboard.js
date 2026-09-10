// Language-specific keyboards + key-state mirroring from board.

const LAYOUTS = {
  en: [
    ['q','w','e','r','t','y','u','i','o','p'],
    ['a','s','d','f','g','h','j','k','l'],
    ['ENTER','z','x','c','v','b','n','m','BACK'],
  ],
  tr: [
    ['q','w','e','r','t','y','u','ı','o','p','ğ','ü'],
    ['a','s','d','f','g','h','j','k','l','ş','i'],
    ['ENTER','z','x','c','v','b','n','m','ö','ç','BACK'],
  ],
  de: [
    ['q','w','e','r','t','z','u','i','o','p','ü'],
    ['a','s','d','f','g','h','j','k','l','ö','ä'],
    ['ENTER','y','x','c','v','b','n','m','ß','BACK'],
  ],
};

const PRIORITY = { green: 3, yellow: 2, gray: 1 };

export function buildKeyboard(root, language, onKey) {
  root.innerHTML = '';
  const layout = LAYOUTS[language] || LAYOUTS.en;
  for (const row of layout) {
    const rowEl = document.createElement('div');
    rowEl.className = 'kb-row';
    for (const key of row) {
      const btn = document.createElement('button');
      btn.className = 'kb-key';
      btn.type = 'button';
      btn.dataset.key = key;
      if (key === 'ENTER' || key === 'BACK') {
        btn.classList.add('kb-wide');
        btn.textContent = key === 'ENTER' ? 'Enter' : '⌫';
      } else {
        btn.textContent = key;
      }
      btn.addEventListener('click', (ev) => {
        // Ripple origin at click point (or centered on non-mouse events).
        const rect = btn.getBoundingClientRect();
        const x = ((ev.clientX ?? rect.left + rect.width / 2) - rect.left) / rect.width;
        const y = ((ev.clientY ?? rect.top + rect.height / 2) - rect.top) / rect.height;
        btn.style.setProperty('--px', `${x * 100}%`);
        btn.style.setProperty('--py', `${y * 100}%`);
        flashKey(btn);
        onKey(key);
      });
      rowEl.appendChild(btn);
    }
    root.appendChild(rowEl);
  }
}

export function flashKey(btn) {
  btn.classList.remove('is-pressed');
  void btn.offsetWidth; // reflow
  btn.classList.add('is-pressed');
  setTimeout(() => btn.classList.remove('is-pressed'), 260);
}

export function flashKeyByChar(root, ch) {
  const btn = root.querySelector(`.kb-key[data-key="${ch}"]`);
  if (btn) flashKey(btn);
}

export function updateKeyStates(root, guess, mask) {
  // Merge new marks with existing ones, keep the strongest.
  for (let i = 0; i < guess.length; i++) {
    const ch = guess[i];
    const m = mask[i];
    const btn = root.querySelector(`.kb-key[data-key="${ch}"]`);
    if (!btn) continue;
    const current = ['green', 'yellow', 'gray'].find((k) => btn.classList.contains(`is-${k}`));
    if (current && PRIORITY[current] >= PRIORITY[m]) continue;
    btn.classList.remove('is-green', 'is-yellow', 'is-gray');
    btn.classList.add(`is-${m}`);
  }
}
