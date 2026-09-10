/* Pointer-following pull on buttons.
 *
 * One delegated listener writing two custom properties, rather than a
 * transform per element per frame. Skipped entirely on coarse pointers, where
 * there is no cursor to follow and the effect would only ever fire as a stuck
 * state after a tap.
 */

import { prefersReducedMotion } from '/js/theme.js';

const FINE_POINTER = window.matchMedia('(hover: hover) and (pointer: fine)');

export function enableMagneticButtons(root = document) {
  if (!FINE_POINTER.matches || prefersReducedMotion()) return;

  root.addEventListener('pointermove', (event) => {
    const button = event.target.closest('.btn');
    if (!button) return;
    const rect = button.getBoundingClientRect();
    // -1..1 from the centre of the button.
    button.style.setProperty('--pull-x', ((event.clientX - rect.left) / rect.width - 0.5) * 2);
    button.style.setProperty('--pull-y', ((event.clientY - rect.top) / rect.height - 0.5) * 2);
  });

  root.addEventListener('pointerleave', (event) => {
    const button = event.target.closest && event.target.closest('.btn');
    if (!button) return;
    button.style.removeProperty('--pull-x');
    button.style.removeProperty('--pull-y');
  }, true);
}
