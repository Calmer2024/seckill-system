import { Icon } from '@iconify/react';
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

export function ProductArtwork({ product, compact = false }) {
  return (
    <div
      className={[
        'product-artwork relative overflow-hidden rounded-[1.5rem] bg-[#f5f5f7]',
        compact ? 'aspect-[4/3]' : 'aspect-[5/4]',
      ].join(' ')}
    >
      <img src={product.imageUrl} alt={product.name} loading="lazy" className="product-artwork-image h-full w-full object-cover" />
    </div>
  );
}

export default function ProductCard({
  product,
  quickActionLabel = '查看详情',
  quickActionTo = `/products/${product.id}`,
  primaryActionLabel = '立即抢购',
  primaryActionTo = `/flash-sale/${product.id}`,
  compact = false,
  revealIndex = 0,
}) {
  const navigate = useNavigate();

  const handleCardNavigate = () => {
    navigate(quickActionTo);
  };

  return (
    <article
      role="link"
      tabIndex={0}
      onClick={handleCardNavigate}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handleCardNavigate();
        }
      }}
      aria-label={`查看${product.name}详情`}
      className="product-card group cursor-pointer overflow-hidden rounded-[1.8rem] bg-[#f5f5f7] p-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0071e3]"
      style={{ '--reveal-index': revealIndex }}
    >
      <ProductArtwork product={product} compact={compact} />

      <div className="px-3 pb-3 pt-5 md:px-4">
        <p className="text-[0.7rem] font-semibold tracking-[0.09em] text-[#6e6e73]">{product.categoryLabel}</p>
        <h3 className="mt-2 min-h-[3.1rem] text-[1.35rem] font-semibold leading-[1.2] tracking-[-0.035em] text-[#1d1d1f]">{product.name}</h3>
        <p className="mt-2 line-clamp-1 text-[0.82rem] leading-6 text-[#6e6e73]">{product.highlight}</p>
        <div className="mt-5 flex items-end justify-between gap-3 border-t border-black/8 pt-4">
          <div><p className="text-[0.72rem] text-[#6e6e73]">秒杀价</p><p className="mt-0.5 text-[1.55rem] font-semibold tracking-[-0.045em] text-[#1d1d1f] tabular-nums">¥{product.priceLabel}</p></div>
          <span className="pb-1 text-xs text-[#6e6e73]">{product.stockLabel}</span>
        </div>
      </div>

      <div className="flex items-center gap-4 px-6 pb-5 text-[0.82rem] font-medium md:px-7">
        <Link
          to={quickActionTo}
          onClick={(event) => event.stopPropagation()}
          className="inline-flex items-center gap-1 text-[#0066cc] hover:underline"
        >
          {quickActionLabel}<Icon icon="lucide:chevron-right" className="h-3.5 w-3.5" />
        </Link>
        <Link
          to={primaryActionTo}
          onClick={(event) => event.stopPropagation()}
          className="rounded-full bg-[#1d1d1f] px-4 py-2 text-white transition-colors hover:bg-[#424245]"
        >
          {primaryActionLabel}
        </Link>
      </div>
    </article>
  );
}
