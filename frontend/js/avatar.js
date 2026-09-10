/* Pixel avatar.
 *
 * Built with createElementNS rather than by concatenating an SVG string. The
 * string version interpolated colour values straight into markup; every value
 * happened to come from a frozen map today, but `renderAvatar` is called with
 * `profile.avatar_config` straight off the API, so it was one careless change
 * away from being an injection point.
 */

import { prefersReducedMotion } from '/js/theme.js';

const NS = 'http://www.w3.org/2000/svg';

export const SHIRT_COLORS = [
  '#3CCB7F', '#62E6FF', '#FF5DA2', '#8D7CFF', '#F4C95D',
  '#FF6B6B', '#4ECDC4', '#F79F79', '#B8B8FF', '#7BD389', '#E4E4E7',
];

export const AURA_COLORS = ['#62E6FF', '#3CCB7F', '#FF5DA2', '#8D7CFF', '#F4C95D', '#FF6B6B'];

export const HAIR_STYLES = {
  short_black: { color: '#1B1B22', height: 4 },
  short_brown: { color: '#5A3A22', height: 4 },
  long_blond: { color: '#E8C87A', height: 7 },
  curly_red: { color: '#B84A2B', height: 5 },
  buzz: { color: '#2F2F38', height: 2 },
  none: { color: null, height: 0 },
};

export const ACCESSORIES = ['badge', 'glasses', 'crown', 'headphones', 'scarf', 'calculator', 'book'];

const SKIN = '#E8B98A';
const INK = '#062015';

function svgEl(name, attrs) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) node.setAttribute(key, String(value));
  }
  return node;
}

function pick(list, value, fallback) {
  return list.includes(value) ? value : fallback;
}

/**
 * @param {object} config  {hair, accessory, shirt, aura, name}
 * @param {string} type    'default' | 'custom'
 * @returns {SVGSVGElement}
 */
export function renderAvatar(config = {}, type = 'custom') {
  const isDefault = type === 'default';
  const hairKey = isDefault
    ? 'short_black'
    : (HAIR_STYLES[config.hair] ? config.hair : 'short_black');
  const hair = HAIR_STYLES[hairKey];
  const shirt = isDefault ? SHIRT_COLORS[0] : pick(SHIRT_COLORS, config.shirt, SHIRT_COLORS[0]);
  const aura = isDefault ? AURA_COLORS[1] : pick(AURA_COLORS, config.aura, AURA_COLORS[0]);
  const accessory = isDefault ? 'badge' : pick(ACCESSORIES, config.accessory, 'badge');

  const svg = svgEl('svg', {
    viewBox: '0 0 32 32',
    class: 'avatar',
    'shape-rendering': 'crispEdges',
    role: 'img',
    'aria-label': config.name ? String(config.name) : 'avatar',
    focusable: 'false',
  });

  // Aura
  const auraRing = svgEl('circle', {
    cx: 16, cy: 16, r: 14, fill: 'none', stroke: aura, 'stroke-width': 1.5,
    'stroke-opacity': 0.5,
  });
  if (!prefersReducedMotion()) {
    // SMIL, so it needs the reduced-motion check in JS — a CSS
    // `animation-duration: 0` cannot stop an <animate> element, which is why
    // the old aura pulsed forever regardless of the setting.
    auraRing.appendChild(
      svgEl('animate', {
        attributeName: 'stroke-opacity',
        values: '0.5;0.15;0.5',
        dur: '3s',
        repeatCount: 'indefinite',
      })
    );
  }
  svg.appendChild(auraRing);

  // Head, hair, eyes, body
  svg.appendChild(svgEl('rect', { x: 10, y: 8, width: 12, height: 11, fill: SKIN }));
  if (hair.color) {
    svg.appendChild(
      svgEl('rect', { x: 9, y: 6, width: 14, height: hair.height, fill: hair.color })
    );
    if (hairKey === 'long_blond') {
      svg.appendChild(svgEl('rect', { x: 9, y: 6, width: 2, height: 12, fill: hair.color }));
      svg.appendChild(svgEl('rect', { x: 21, y: 6, width: 2, height: 12, fill: hair.color }));
    }
  }
  svg.appendChild(svgEl('rect', { x: 12, y: 12, width: 2, height: 2, fill: INK }));
  svg.appendChild(svgEl('rect', { x: 18, y: 12, width: 2, height: 2, fill: INK }));
  svg.appendChild(svgEl('rect', { x: 14, y: 16, width: 4, height: 1, fill: '#8A5A3C' }));
  svg.appendChild(svgEl('rect', { x: 8, y: 19, width: 16, height: 9, fill: shirt }));
  svg.appendChild(svgEl('rect', { x: 6, y: 20, width: 2, height: 6, fill: SKIN }));
  svg.appendChild(svgEl('rect', { x: 24, y: 20, width: 2, height: 6, fill: SKIN }));

  for (const node of accessoryNodes(accessory, aura)) svg.appendChild(node);
  return svg;
}

function accessoryNodes(accessory, aura) {
  switch (accessory) {
    case 'glasses':
      return [
        svgEl('rect', { x: 11, y: 11, width: 4, height: 4, fill: 'none', stroke: INK }),
        svgEl('rect', { x: 17, y: 11, width: 4, height: 4, fill: 'none', stroke: INK }),
        svgEl('rect', { x: 15, y: 12, width: 2, height: 1, fill: INK }),
      ];
    case 'crown':
      return [
        svgEl('path', { d: 'M9 6 L11 2 L13 5 L16 1 L19 5 L21 2 L23 6 Z', fill: '#F4C95D' }),
      ];
    case 'headphones':
      return [
        svgEl('path', { d: 'M9 12 A7 7 0 0 1 23 12', fill: 'none', stroke: '#2F2F38', 'stroke-width': 2 }),
        svgEl('rect', { x: 7, y: 12, width: 3, height: 5, fill: '#2F2F38' }),
        svgEl('rect', { x: 22, y: 12, width: 3, height: 5, fill: '#2F2F38' }),
      ];
    case 'scarf':
      return [
        svgEl('rect', { x: 10, y: 18, width: 12, height: 2, fill: '#FF5DA2' }),
        svgEl('rect', { x: 14, y: 20, width: 2, height: 5, fill: '#FF5DA2' }),
      ];
    case 'calculator':
      return [
        svgEl('rect', { x: 12, y: 21, width: 8, height: 6, fill: '#1E2438' }),
        svgEl('rect', { x: 13, y: 22, width: 6, height: 2, fill: '#62E6FF' }),
      ];
    case 'book':
      return [
        svgEl('rect', { x: 11, y: 22, width: 10, height: 6, fill: '#8D7CFF' }),
        svgEl('rect', { x: 15, y: 22, width: 1, height: 6, fill: '#1E2438' }),
      ];
    case 'badge':
    default:
      return [
        svgEl('circle', { cx: 12, cy: 22, r: 2, fill: aura }),
        svgEl('text', {
          x: 12, y: 23.4, 'text-anchor': 'middle', 'font-size': 3,
          'font-family': 'monospace', 'font-weight': 'bold', fill: INK,
        }),
      ].map((node, index) => {
        if (index === 1) node.textContent = 'O';
        return node;
      });
  }
}

/** Replace an element's contents with a freshly rendered avatar. */
export function mountAvatar(el, config, type) {
  el.replaceChildren(renderAvatar(config, type));
}
