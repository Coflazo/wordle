/* Decorative starfield on the welcome screen.
 *
 * Rewritten for cost. The previous loop, every frame, forever: cleared the full
 * DPR-scaled canvas, wrote about 330 context-state properties to draw ~112
 * shapes, re-parsed the canvas font shorthand up to eight times (480 parses a
 * second at 60Hz, 960 on a 120Hz display), and allocated a fresh array. It also
 * used per-frame velocity constants, so everything moved at double speed on a
 * ProMotion display, and its resize handler was unthrottled — each event
 * reallocated the GPU backing store and re-randomized all 104 objects, so
 * scrolling on mobile made the stars visibly teleport.
 */

import { prefersReducedMotion, onReducedMotionChange } from '/js/theme.js';

const canvas = document.getElementById('pixel-bg');

if (canvas) {
  const ctx = canvas.getContext('2d', { alpha: true });

  const STAR_COUNT = 70;
  const SQUARE_COUNT = 12;
  const LETTERS = 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZÄÖÜSS';
  const PALETTE = ['#3CCB7F', '#F4C95D', '#62E6FF', '#8D7CFF', '#FF5DA2'];
  const STAR_COLOR = '#c9d1e2';

  const state = {
    w: 0, h: 0, dpr: 1,
    stars: [], squares: [], letters: [],
    lastLetterAt: 0, lastFrame: 0,
    running: false, raf: 0,
  };

  const rand = (min, max) => min + Math.random() * (max - min);

  function seed() {
    state.stars = Array.from({ length: STAR_COUNT }, () => ({
      x: rand(0, state.w), y: rand(0, state.h),
      size: Math.random() < 0.8 ? 1 : 2,
      // Speeds are per second, and the loop multiplies by elapsed time, so the
      // scene moves at the same rate on a 30Hz and a 120Hz display.
      vy: rand(5, 14),
      alpha: rand(0.25, 0.8),
    }));
    state.squares = Array.from({ length: SQUARE_COUNT }, () => ({
      x: rand(0, state.w), y: rand(0, state.h),
      size: rand(8, 26),
      vx: rand(-9, 9), vy: rand(-6, 6),
      color: PALETTE[Math.floor(rand(0, PALETTE.length))],
      alpha: rand(0.05, 0.16),
    }));
    state.letters = [];
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === state.w && h === state.h && dpr === state.dpr) return;

    const isFirst = state.w === 0;
    // Keep everything proportionally in place instead of re-seeding, which is
    // what made stars jump whenever a mobile address bar collapsed.
    const scaleX = state.w ? w / state.w : 1;
    const scaleY = state.h ? h / state.h : 1;

    state.w = w;
    state.h = h;
    state.dpr = dpr;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (isFirst) {
      seed();
    } else {
      for (const list of [state.stars, state.squares, state.letters]) {
        for (const item of list) {
          item.x *= scaleX;
          item.y *= scaleY;
        }
      }
    }
  }

  function spawnLetter(now) {
    if (now - state.lastLetterAt < 1100 || state.letters.length >= 6) return;
    state.lastLetterAt = now;
    const size = rand(14, 30);
    state.letters.push({
      char: LETTERS[Math.floor(rand(0, LETTERS.length))],
      x: rand(0, Math.max(1, state.w - size)),
      y: -size,
      size,
      // Built once at spawn rather than reassembled every frame. Assigning
      // ctx.font re-runs the CSS font shorthand parser and a font match.
      font: `700 ${Math.round(size)}px "JetBrains Mono", ui-monospace, monospace`,
      vy: rand(24, 48),
      color: PALETTE[Math.floor(rand(0, PALETTE.length))],
      alpha: rand(0.1, 0.26),
    });
  }

  function step(now) {
    const dt = Math.min((now - state.lastFrame) / 1000, 0.05);
    state.lastFrame = now;

    ctx.clearRect(0, 0, state.w, state.h);

    ctx.fillStyle = STAR_COLOR;
    for (const star of state.stars) {
      star.y += star.vy * dt;
      if (star.y > state.h) {
        star.y = -2;
        star.x = rand(0, state.w);
      }
      ctx.globalAlpha = star.alpha;
      ctx.fillRect(star.x | 0, star.y | 0, star.size, star.size);
    }

    ctx.lineWidth = 1;
    for (const square of state.squares) {
      square.x += square.vx * dt;
      square.y += square.vy * dt;
      if (square.x < -square.size) square.x = state.w;
      if (square.x > state.w) square.x = -square.size;
      if (square.y < -square.size) square.y = state.h;
      if (square.y > state.h) square.y = -square.size;
      ctx.globalAlpha = square.alpha;
      ctx.strokeStyle = square.color;
      ctx.strokeRect(square.x | 0, square.y | 0, square.size, square.size);
    }

    spawnLetter(now);
    let alive = 0;
    for (const letter of state.letters) {
      letter.y += letter.vy * dt;
      if (letter.y <= state.h + letter.size) {
        state.letters[alive] = letter;
        alive += 1;
        ctx.globalAlpha = letter.alpha;
        ctx.fillStyle = letter.color;
        ctx.font = letter.font;
        ctx.fillText(letter.char, letter.x, letter.y);
      }
    }
    // Truncate in place rather than allocating a new array every frame.
    state.letters.length = alive;

    ctx.globalAlpha = 1;
    state.raf = requestAnimationFrame(step);
  }

  function start() {
    if (state.running) return;
    state.running = true;
    state.lastFrame = performance.now();
    state.raf = requestAnimationFrame(step);
  }

  function stop() {
    state.running = false;
    cancelAnimationFrame(state.raf);
    ctx.clearRect(0, 0, state.w, state.h);
  }

  function drawStatic() {
    ctx.clearRect(0, 0, state.w, state.h);
    ctx.fillStyle = STAR_COLOR;
    for (const star of state.stars) {
      ctx.globalAlpha = star.alpha * 0.7;
      ctx.fillRect(star.x | 0, star.y | 0, star.size, star.size);
    }
    ctx.globalAlpha = 1;
  }

  function sync() {
    if (prefersReducedMotion()) {
      stop();
      drawStatic();
    } else if (document.visibilityState === 'visible') {
      start();
    } else {
      stop();
    }
  }

  // Coalesce resize bursts into one frame. A desktop window drag fires dozens
  // of these a second.
  let resizeQueued = false;
  const onResize = () => {
    if (resizeQueued) return;
    resizeQueued = true;
    requestAnimationFrame(() => {
      resizeQueued = false;
      resize();
      if (!state.running) drawStatic();
    });
  };

  if ('ResizeObserver' in window) {
    new ResizeObserver(onResize).observe(canvas);
  } else {
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
  }

  document.addEventListener('visibilitychange', sync);
  onReducedMotionChange(sync);

  resize();
  sync();
}
