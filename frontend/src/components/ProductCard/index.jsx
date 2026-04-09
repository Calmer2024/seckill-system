import { Icon } from '@iconify/react';
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

export function ProductArtwork({ product, compact = false }) {
  return (
    <div
      className={[
        'relative overflow-hidden rounded-[2rem] border border-[#F0F0F0] bg-[linear-gradient(180deg,#F8F8F8_0%,#F1F1F1_100%)]',
        compact ? 'h-48 p-5' : 'h-60 p-6',
      ].join(' ')}
    >
      <div className="absolute inset-x-[18%] top-5 h-8 rounded-full bg-white/70 blur-2xl" />
      <div className="absolute inset-x-[26%] bottom-5 h-6 rounded-full bg-black/8 blur-xl" />
      <div className="absolute -right-8 top-4 h-28 w-28 rounded-full bg-white/50 blur-3xl" />
      <div className="relative flex h-full items-center justify-center">
        <div
          className={[
            'flex items-center justify-center rounded-[2rem] border border-white/80 bg-white shadow-[0_26px_50px_-24px_rgba(17,24,39,0.28)]',
            compact ? 'h-28 w-28' : 'h-36 w-36',
          ].join(' ')}
        >
          <Icon
            icon={product.visualIcon || 'lucide:package-open'}
            className={compact ? 'h-14 w-14 text-primary' : 'h-16 w-16 text-primary'}
          />
        </div>
      </div>
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
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handleCardNavigate();
        }
      }}
      className="cursor-pointer rounded-[2rem] border border-[#EEEEEE] bg-white p-4 shadow-[0_18px_45px_-38px_rgba(17,24,39,0.22)] transition-transform duration-300 hover:-translate-y-1"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-full bg-[#F6F6F6] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {product.categoryBadge}
        </span>
        <span className="rounded-full border border-[#EEEEEE] bg-white px-3 py-1 text-[11px] font-medium text-text-muted">
          {product.highlight}
        </span>
      </div>

      <ProductArtwork product={product} compact={compact} />

      <div className="mt-4">
        <h3 className="text-[1.1rem] font-bold tracking-[-0.03em] text-primary">{product.name}</h3>
        <div className="mt-2 flex items-center gap-2 text-xs text-text-muted">
          <Icon icon="lucide:star" className="h-4 w-4 text-accent-yellow" />
          <span>{product.rating}</span>
          <span>({product.reviewsLabel})</span>
        </div>
        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <div className="text-xs text-text-muted">{product.categoryLabel}</div>
            <div className="text-2xl font-black tracking-[-0.05em] text-primary">¥{product.priceLabel}</div>
          </div>
          <div className="text-right text-xs text-text-muted">{product.stockLabel}</div>
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <Link
          to={quickActionTo}
          onClick={(event) => event.stopPropagation()}
          className="flex-1 rounded-full border border-[#E5E7EB] bg-white px-4 py-3 text-center text-sm font-semibold text-primary transition-colors hover:bg-[#F5F5F5]"
        >
          {quickActionLabel}
        </Link>
        <Link
          to={primaryActionTo}
          onClick={(event) => event.stopPropagation()}
          className="flex-1 rounded-full bg-primary px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-primary-light"
        >
          {primaryActionLabel}
        </Link>
      </div>
    </article>
  );
}
