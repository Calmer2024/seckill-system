const DEFAULT_AVATAR_URL = '/avatar.JPG';

function buildAvatarDataUri({ backgroundStart, backgroundEnd, accent, label }) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
          <stop stop-color="${backgroundStart}" />
          <stop offset="1" stop-color="${backgroundEnd}" />
        </linearGradient>
      </defs>
      <rect width="120" height="120" rx="34" fill="url(#g)" />
      <circle cx="60" cy="44" r="18" fill="rgba(255,255,255,0.92)" />
      <path d="M28 95c4.4-16.8 17.8-25.2 32-25.2S87.6 78.2 92 95" fill="rgba(255,255,255,0.92)" />
      <circle cx="92" cy="30" r="8" fill="${accent}" fill-opacity="0.88" />
      <text x="60" y="112" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="12" fill="rgba(255,255,255,0.82)">${label}</text>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export const avatarPresets = [
  { id: 'classic', label: '默认', url: DEFAULT_AVATAR_URL },
  {
    id: 'sunrise',
    label: '暖橙',
    url: buildAvatarDataUri({
      backgroundStart: '#F5C07A',
      backgroundEnd: '#D96B43',
      accent: '#FFF1B8',
      label: 'SUN',
    }),
  },
  {
    id: 'sage',
    label: '苔绿',
    url: buildAvatarDataUri({
      backgroundStart: '#8EB69B',
      backgroundEnd: '#4D6B56',
      accent: '#E7F4D7',
      label: 'SAGE',
    }),
  },
  {
    id: 'midnight',
    label: '夜蓝',
    url: buildAvatarDataUri({
      backgroundStart: '#51617A',
      backgroundEnd: '#202A3B',
      accent: '#B8CCE8',
      label: 'NITE',
    }),
  },
  {
    id: 'pearl',
    label: '银白',
    url: buildAvatarDataUri({
      backgroundStart: '#DDD9D4',
      backgroundEnd: '#B6B0A8',
      accent: '#FFFFFF',
      label: 'PEARL',
    }),
  },
];

export { DEFAULT_AVATAR_URL };
