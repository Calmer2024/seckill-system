const CATEGORY_DEFINITIONS = [
  { key: 'all', label: '全部商品', icon: 'lucide:grid-2x2' },
  { key: 'home', label: '居家好物', icon: 'lucide:house' },
  { key: 'music', label: '音乐设备', icon: 'lucide:music' },
  { key: 'desk', label: '桌面办公', icon: 'lucide:monitor' },
  { key: 'kitchen', label: '厨房电器', icon: 'lucide:chef-hat' },
  { key: 'wellness', label: '个护舒缓', icon: 'lucide:sparkles' },
];

const QUICK_FILTERS = [
  { key: 'new', label: '新品优先', icon: 'lucide:sparkles' },
  { key: 'best', label: '高分推荐', icon: 'lucide:award' },
  { key: 'discount', label: '秒杀折扣', icon: 'lucide:tag' },
];

function formatRating(value) {
  return Number(value || 0).toFixed(1);
}

export function getCategoryDefinitions() {
  return CATEGORY_DEFINITIONS;
}

export function getQuickFilters() {
  return QUICK_FILTERS;
}

export function decorateProduct(product, index = 0) {
  const safeCategory = product.category || CATEGORY_DEFINITIONS[(index % (CATEGORY_DEFINITIONS.length - 1)) + 1].key;
  const category = CATEGORY_DEFINITIONS.find((item) => item.key === safeCategory);
  const tags = Array.isArray(product.tags) ? product.tags : [];
  const firstTag = tags[0] || category?.label || '好物';
  const availableStock = product.available_stock ?? product.stock ?? 0;

  return {
    ...product,
    priceLabel: Number(product.price || 0).toFixed(2),
    stockLabel: `${availableStock} 件库存`,
    categoryKey: safeCategory,
    categoryLabel: category?.label || '全部商品',
    categoryBadge: category?.label || firstTag,
    visualIcon: product.visual_icon || 'lucide:package-open',
    highlight: product.highlight || firstTag,
    description: product.summary || '正在整理这件商品的详细介绍。',
    rating: formatRating(product.rating),
    reviewsLabel: `${Number(product.review_count || 0)} 条评价`,
    tags,
    availableStock,
  };
}

export function buildProductSummary(product) {
  return `${product.categoryLabel} · ${product.highlight}`;
}
