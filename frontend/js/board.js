// Board factory: builds and updates the adaptive tile grid.

export function buildBoard(root, rows, cols) {
  root.innerHTML = '';
  root.style.setProperty('--cols', cols);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const tile = document.createElement('div');
      tile.className = 'tile';
      tile.dataset.row = String(r);
      tile.dataset.col = String(c);
      root.appendChild(tile);
    }
  }
}

export function tileAt(root, row, col) {
  return root.querySelector(`.tile[data-row="${row}"][data-col="${col}"]`);
}

export function setTypedRow(root, row, letters, cols) {
  for (let c = 0; c < cols; c++) {
    const tile = tileAt(root, row, c);
    if (!tile) continue;
    const ch = letters[c] || '';
    tile.textContent = ch;
    tile.classList.toggle('is-filled', Boolean(ch));
  }
}

export function revealRow(root, row, letters, mask) {
  for (let c = 0; c < letters.length; c++) {
    const tile = tileAt(root, row, c);
    if (!tile) continue;
    const ch = letters[c];
    const m = mask[c];
    setTimeout(() => {
      // Store lowercase; CSS `text-transform: uppercase` on `.tile` handles
      // display casing, and respects the ancestor `lang` attribute so
      // Turkish maps i → İ and ı → I correctly.
      tile.textContent = ch;
      tile.classList.add('is-flipping');
      setTimeout(() => {
        tile.classList.remove('is-filled');
        tile.classList.add(`is-${m}`);
      }, 175);
      setTimeout(() => tile.classList.remove('is-flipping'), 360);
    }, c * 120);
  }
}

export function shakeRow(root) {
  root.classList.add('is-shaking');
  setTimeout(() => root.classList.remove('is-shaking'), 260);
}

export function pixelBurst() {
  const layer = document.createElement('div');
  layer.className = 'burst';
  document.body.appendChild(layer);
  const colors = ['#3CCB7F', '#F4C95D', '#62E6FF', '#8D7CFF', '#FF5DA2'];
  for (let i = 0; i < 80; i++) {
    const px = document.createElement('div');
    px.className = 'pixel';
    const angle = Math.random() * Math.PI * 2;
    const dist = 80 + Math.random() * 260;
    px.style.background = colors[i % colors.length];
    px.style.left = `${50 + (Math.random() - 0.5) * 8}%`;
    px.style.top = `${50 + (Math.random() - 0.5) * 8}%`;
    px.style.setProperty('--dx', `${Math.cos(angle) * dist}px`);
    px.style.setProperty('--dy', `${Math.sin(angle) * dist}px`);
    layer.appendChild(px);
  }
  setTimeout(() => layer.remove(), 1000);
}
