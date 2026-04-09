const CATEGORY_DEFINITIONS = [
  { key: 'all', label: '全部商品', icon: 'lucide:grid-2x2' },
  { key: 'home', label: '居家好物', icon: 'lucide:house' },
  { key: 'music', label: '音乐设备', icon: 'lucide:music' },
  { key: 'desk', label: '桌面办公', icon: 'lucide:monitor' },
  { key: 'storage', label: '清洁收纳', icon: 'lucide:package-open' },
];

const QUICK_FILTERS = [
  { key: 'new', label: '新品优先', icon: 'lucide:sparkles' },
  { key: 'best', label: '高分推荐', icon: 'lucide:award' },
  { key: 'discount', label: '秒杀折扣', icon: 'lucide:tag' },
];

const PRODUCT_PRESETS = [
  {
    match: ['cleaner', 'adudu'],
    categoryKey: 'storage',
    categoryBadge: 'Other',
    visualIcon: 'lucide:disc-3',
    highlight: '机器人清洁',
    description: '适合客厅与卧室的静音清洁设备，支持秒杀直购与库存实时查询。',
    rating: 4.9,
    reviews: 124,
  },
  {
    match: ['earbuds', 'head', 'audio'],
    categoryKey: 'music',
    categoryBadge: 'Music',
    visualIcon: 'lucide:headphones',
    highlight: '沉浸音频',
    description: '轻量耳机与耳塞系列，强调佩戴舒适度与日常移动场景。',
    rating: 5,
    reviews: 82,
  },
  {
    match: ['stream', 'stick', 'holder', 'phone'],
    categoryKey: 'desk',
    categoryBadge: 'Other',
    visualIcon: 'lucide:smartphone',
    highlight: '桌面效率',
    description: '偏向桌面与影音使用场景，适合作为办公与娱乐混合设备。',
    rating: 4.8,
    reviews: 63,
  },
  {
    match: ['cctv', 'camera'],
    categoryKey: 'home',
    categoryBadge: 'Home',
    visualIcon: 'lucide:camera',
    highlight: '居家守护',
    description: '家庭场景常用的智能监控与感应设备，适合全天候守护。',
    rating: 4.8,
    reviews: 96,
  },
];

function fallbackPreset(index) {
  const presets = [
    PRODUCT_PRESETS[0],
    PRODUCT_PRESETS[1],
    PRODUCT_PRESETS[2],
    PRODUCT_PRESETS[3],
  ];
  return presets[index % presets.length];
}

function pickPreset(product, index) {
  const target = `${product.name || ''}`.toLowerCase();
  const matched = PRODUCT_PRESETS.find((item) =>
    item.match.some((keyword) => target.includes(keyword))
  );
  return matched || fallbackPreset(index);
}

function formatRating(value) {
  return Number(value).toFixed(1);
}

export function getCategoryDefinitions() {
  return CATEGORY_DEFINITIONS;
}

export function getQuickFilters() {
  return QUICK_FILTERS;
}

export function decorateProduct(product, index = 0) {
  const preset = pickPreset(product, index);
  const category = CATEGORY_DEFINITIONS.find((item) => item.key === preset.categoryKey);

  return {
    ...product,
    priceLabel: Number(product.price || 0).toFixed(2),
    stockLabel: `${product.stock ?? 0} 件库存`,
    categoryKey: preset.categoryKey,
    categoryLabel: category?.label || '全部商品',
    categoryBadge: preset.categoryBadge,
    visualIcon: preset.visualIcon,
    highlight: preset.highlight,
    description: preset.description,
    rating: formatRating(preset.rating),
    reviewsLabel: `${preset.reviews} 条评价`,
  };
}

export function buildProductSummary(product) {
  return `${product.categoryLabel} · ${product.highlight}`;
}
