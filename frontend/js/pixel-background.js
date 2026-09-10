// Atari-style animated background: starfield + drifting neon squares + falling letters.
// Draws to <canvas id="pixel-bg">. Honors prefers-reduced-motion.

const canvas = document.getElementById('pixel-bg');
if (canvas) {
  const ctx = canvas.getContext('2d');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = {
    w: 0,
    h: 0,
    dpr: Math.min(window.devicePixelRatio || 1, 2),
    stars: [],
    squares: [],
    letters: [],
    langLetters: ['A', 'E', 'İ', 'Ö', 'Ü', 'Ç', 'S', 'K', 'M', 'L', 'B', 'R', 'Ä', 'ß', 'T', 'O'],
    lastLetter: 0,
    running: !reduced,
  };

  function resize() {
    // Prefer the viewport as the sizing source — the canvas is position:fixed
    // and should always fill it. Fall back to bounding-rect otherwise.
    const w = window.innerWidth || document.documentElement.clientWidth;
    const h = window.innerHeight || document.documentElement.clientHeight;
    state.w = w;
    state.h = h;
    canvas.width = Math.max(1, Math.floor(w * state.dpr));
    canvas.height = Math.max(1, Math.floor(h * state.dpr));
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    seed();
  }

  function seed() {
    state.stars = [];
    for (let i = 0; i < 90; i++) {
      state.stars.push({
        x: Math.random() * state.w,
        y: Math.random() * state.h,
        r: Math.random() < 0.75 ? 1 : 2,
        vy: 0.08 + Math.random() * 0.16,
        alpha: 0.4 + Math.random() * 0.6,
      });
    }
    state.squares = [];
    for (let i = 0; i < 14; i++) {
      state.squares.push({
        x: Math.random() * state.w,
        y: Math.random() * state.h,
        s: 6 + Math.random() * 22,
        vx: (Math.random() - 0.5) * 0.24,
        vy: (Math.random() - 0.5) * 0.18,
        c: ['#62E6FF', '#8D7CFF', '#FF5DA2', '#3CCB7F'][Math.floor(Math.random() * 4)],
        a: 0.05 + Math.random() * 0.12,
      });
    }
  }

  function spawnLetter() {
    state.letters.push({
      ch: state.langLetters[Math.floor(Math.random() * state.langLetters.length)],
      x: Math.random() * state.w,
      y: -20,
      vy: 0.35 + Math.random() * 0.5,
      alpha: 0.65,
      color: ['#62E6FF', '#8D7CFF', '#3CCB7F'][Math.floor(Math.random() * 3)],
      size: 14 + Math.floor(Math.random() * 12),
    });
  }

  function step(t) {
    if (!state.running) return;
    ctx.clearRect(0, 0, state.w, state.h);

    // Stars
    for (const s of state.stars) {
      s.y += s.vy;
      if (s.y > state.h) { s.y = -2; s.x = Math.random() * state.w; }
      ctx.globalAlpha = s.alpha;
      ctx.fillStyle = '#c9d1e2';
      ctx.fillRect(s.x, s.y, s.r, s.r);
    }

    // Neon squares
    for (const q of state.squares) {
      q.x += q.vx; q.y += q.vy;
      if (q.x < -q.s) q.x = state.w + q.s;
      if (q.x > state.w + q.s) q.x = -q.s;
      if (q.y < -q.s) q.y = state.h + q.s;
      if (q.y > state.h + q.s) q.y = -q.s;
      ctx.globalAlpha = q.a;
      ctx.strokeStyle = q.c;
      ctx.lineWidth = 1;
      ctx.strokeRect(q.x, q.y, q.s, q.s);
    }

    // Falling letters (sparse)
    if (t - state.lastLetter > 900 && state.letters.length < 8) {
      spawnLetter();
      state.lastLetter = t;
    }
    for (const l of state.letters) {
      l.y += l.vy;
      ctx.globalAlpha = l.alpha;
      ctx.fillStyle = l.color;
      ctx.font = `700 ${l.size}px "JetBrains Mono", ui-monospace, monospace`;
      ctx.fillText(l.ch, l.x, l.y);
    }
    state.letters = state.letters.filter((l) => l.y < state.h + 30);

    ctx.globalAlpha = 1;
    requestAnimationFrame(step);
  }

  // Kick off. Re-resize at multiple lifecycle points so late-loading CSS or
  // font-driven layout shifts can't leave us stuck at the intrinsic 300x150.
  resize();
  requestAnimationFrame(resize);
  window.addEventListener('load', resize);
  window.addEventListener('resize', resize);
  window.addEventListener('orientationchange', resize);

  if (!reduced) {
    requestAnimationFrame(step);
  } else {
    // Static frame so the page isn't empty.
    ctx.fillStyle = 'rgba(255,255,255,0.03)';
    for (let x = 0; x < state.w; x += 20) ctx.fillRect(x, 0, 1, state.h);
    for (let y = 0; y < state.h; y += 20) ctx.fillRect(0, y, state.w, 1);
  }
}
