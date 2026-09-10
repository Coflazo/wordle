// Renders a pixel avatar from an avatar-config JSON blob into an <svg>.
// Deliberately minimal — one <svg> string, no external assets.

const SHIRT_COLORS = {
  midnight: '#171C2B',
  cyan: '#62E6FF',
  pink: '#FF5DA2',
  purple: '#8D7CFF',
  green: '#3CCB7F',
  yellow: '#F4C95D',
};
const AURA_COLORS = {
  'green-glow': '#3CCB7F',
  'cyan-glow': '#62E6FF',
  'pink-glow': '#FF5DA2',
  'purple-glow': '#8D7CFF',
  none: null,
};
const HAIR_STYLES = {
  'short-black': { color: '#0f0f10', shape: 'crown-short' },
  'short-brown': { color: '#5a3a1e', shape: 'crown-short' },
  'long-blond': { color: '#e6c66e', shape: 'crown-long' },
  'curly-red': { color: '#c1462a', shape: 'crown-curly' },
  buzz: { color: '#0f0f10', shape: 'buzz' },
  none: { color: null, shape: 'bald' },
};

function renderHair(hairKey) {
  const h = HAIR_STYLES[hairKey] || HAIR_STYLES['short-black'];
  if (!h.color) return '';
  if (h.shape === 'buzz') {
    return `<rect x="5" y="4" width="10" height="3" fill="${h.color}"/>`;
  }
  if (h.shape === 'crown-long') {
    return `<rect x="4" y="3" width="12" height="5" fill="${h.color}"/><rect x="4" y="8" width="2" height="7" fill="${h.color}"/><rect x="14" y="8" width="2" height="7" fill="${h.color}"/>`;
  }
  if (h.shape === 'crown-curly') {
    return `<rect x="5" y="3" width="10" height="4" fill="${h.color}"/><rect x="4" y="4" width="1" height="2" fill="${h.color}"/><rect x="15" y="4" width="1" height="2" fill="${h.color}"/>`;
  }
  // crown-short (default)
  return `<rect x="5" y="4" width="10" height="4" fill="${h.color}"/>`;
}

function renderAccessory(kind) {
  switch (kind) {
    case 'glasses':
      return `<rect x="6" y="10" width="3" height="2" fill="#f4f7fb"/><rect x="11" y="10" width="3" height="2" fill="#f4f7fb"/><rect x="9" y="11" width="2" height="1" fill="#f4f7fb"/>`;
    case 'crown':
      return `<polygon points="6,3 8,1 10,3 12,1 14,3" fill="#F4C95D"/>`;
    case 'headphones':
      return `<rect x="3" y="8" width="1" height="4" fill="#62E6FF"/><rect x="16" y="8" width="1" height="4" fill="#62E6FF"/><path d="M4 8 Q10 2 16 8" stroke="#62E6FF" stroke-width="1" fill="none"/>`;
    case 'scarf':
      return `<rect x="5" y="16" width="10" height="2" fill="#FF5DA2"/>`;
    case 'calculator':
      return `<rect x="7" y="17" width="6" height="3" fill="#3A4052" stroke="#8B94A7"/>`;
    case 'book':
      return `<rect x="7" y="17" width="6" height="3" fill="#8D7CFF"/><line x1="10" y1="17" x2="10" y2="20" stroke="#f4f7fb" stroke-width="0.4"/>`;
    case 'badge-o':
      return `<circle cx="14" cy="15" r="1.8" fill="#3CCB7F"/><text x="14" y="16" text-anchor="middle" font-size="2.2" font-family="monospace" fill="#062015" font-weight="700">O</text>`;
    default:
      return '';
  }
}

export function renderAvatar(config) {
  const cfg = config || {};
  const shirt = SHIRT_COLORS[cfg.shirt] || SHIRT_COLORS.midnight;
  const auraColor = AURA_COLORS[cfg.aura] || null;

  // Skin: neutral warm.
  const skin = '#f0c9a7';
  const face = `<rect x="6" y="7" width="8" height="7" fill="${skin}"/>`;
  const eyes = `<rect x="8" y="10" width="1" height="1" fill="#0b1220"/><rect x="11" y="10" width="1" height="1" fill="#0b1220"/>`;
  const mouth = `<rect x="9" y="12" width="2" height="1" fill="#0b1220"/>`;
  const neck = `<rect x="8" y="14" width="4" height="2" fill="${skin}"/>`;
  const body = `<rect x="4" y="16" width="12" height="4" fill="${shirt}"/>`;

  const aura = auraColor
    ? `<circle cx="10" cy="10" r="9" fill="none" stroke="${auraColor}" stroke-opacity="0.55" stroke-width="0.7"><animate attributeName="stroke-opacity" values="0.55;0.15;0.55" dur="3s" repeatCount="indefinite"/></circle>`
    : '';

  return `
    <svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" width="100%" height="100%">
      ${aura}
      ${face}
      ${renderHair(cfg.hair)}
      ${eyes}
      ${mouth}
      ${neck}
      ${body}
      ${renderAccessory(cfg.accessory)}
    </svg>
  `;
}

export function mountAvatars(root = document) {
  root.querySelectorAll('.avatar-shell[data-avatar]').forEach((el) => {
    try {
      el.innerHTML = renderAvatar(JSON.parse(el.dataset.avatar));
    } catch (_) {
      el.innerHTML = renderAvatar({});
    }
  });
}

export function setAvatar(el, config) {
  if (!el) return;
  el.innerHTML = renderAvatar(config);
  el.dataset.avatar = JSON.stringify(config);
}
