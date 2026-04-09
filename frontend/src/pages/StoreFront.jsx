import { Icon } from '@iconify/react';
import React, { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import ProductCard from '../components/ProductCard';
import { productApi } from '../services/productApi';
import { decorateProduct, getCategoryDefinitions, getQuickFilters } from '../utils/catalog';

const PAGE_SIZE = 9;

function Pagination({ currentPage, totalPages, onPageChange }) {
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);

  return (
    <div className="mt-8 flex flex-col gap-4 border-t border-[#F0F0F0] pt-6 md:flex-row md:items-center md:justify-between">
      <button
        type="button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="inline-flex items-center gap-2 text-sm font-semibold text-primary disabled:opacity-35"
      >
        <Icon icon="lucide:arrow-left" className="h-4 w-4" />
        上一页
      </button>

      <div className="flex items-center justify-center gap-2">
        {pages.map((page) => (
          <button
            key={page}
            type="button"
            onClick={() => onPageChange(page)}
            className={[
              'flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-colors',
              page === currentPage ? 'bg-primary text-white' : 'bg-[#F7F7F7] text-primary hover:bg-[#EFEFEF]',
            ].join(' ')}
          >
            {page}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="inline-flex items-center justify-end gap-2 text-sm font-semibold text-primary disabled:opacity-35"
      >
        下一页
        <Icon icon="lucide:arrow-right" className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function StoreFront({ session }) {
  const [products, setProducts] = useState([]);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [activeCategory, setActiveCategory] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const deferredKeyword = useDeferredValue(searchKeyword.trim().toLowerCase());
  const categoryDefinitions = getCategoryDefinitions();
  const quickFilters = getQuickFilters();

  useEffect(() => {
    let active = true;

    async function loadProducts() {
      setLoading(true);
      try {
        const response = await productApi.getProducts({ page: 1, size: 100 });
        if (!active) {
          return;
        }
        setProducts(response.map((item, index) => decorateProduct(item, index)));
        setError('');
      } catch (requestError) {
        if (active) {
          setProducts([]);
          setError(requestError?.response?.data?.message || '商品列表加载失败，请稍后再试。');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadProducts();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadSuggestions() {
      if (!searchKeyword.trim()) {
        setSuggestions([]);
        return;
      }

      try {
        const response = await productApi.searchProducts(searchKeyword.trim(), 5);
        if (active) {
          setSuggestions(response.map((item, index) => decorateProduct(item, index)));
        }
      } catch {
        if (active) {
          setSuggestions([]);
        }
      }
    }

    const timer = setTimeout(loadSuggestions, 220);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [searchKeyword]);

  useEffect(() => {
    setCurrentPage(1);
  }, [deferredKeyword, activeCategory]);

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const matchesCategory = activeCategory === 'all' || product.categoryKey === activeCategory;
      const matchesKeyword =
        !deferredKeyword ||
        `${product.name} ${product.categoryLabel} ${product.highlight}`.toLowerCase().includes(deferredKeyword);
      return matchesCategory && matchesKeyword;
    });
  }, [activeCategory, deferredKeyword, products]);

  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / PAGE_SIZE));
  const currentPageProducts = filteredProducts.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const recommendedProducts = products.slice(0, 4);
  const categoryCounts = useMemo(() => {
    return products.reduce(
      (result, item) => {
        result.all += 1;
        result[item.categoryKey] = (result[item.categoryKey] || 0) + 1;
        return result;
      },
      { all: 0 }
    );
  }, [products]);

  return (
    <section className="space-y-24 pb-6">
      <section className="relative overflow-hidden">
        <div
          className="relative h-[520px] w-full bg-cover bg-center md:h-[600px]"
          style={{ backgroundImage: "linear-gradient(180deg, rgba(10,10,10,0.04), rgba(10,10,10,0.04)), url('/bg.jpg')" }}
        >
          <div className="dream-shell relative flex h-full items-start justify-center pt-24 md:pt-28">
            <div className="shop-word select-none text-center text-white">Shop</div>
          </div>
        </div>

        <div className="dream-shell relative z-20 -mt-[152px] md:-mt-[110px]">
          <div className="overflow-visible rounded-[2.5rem] border border-[#ECECEC] bg-white shadow-[0_22px_52px_-42px_rgba(17,24,39,0.22)]">
            <div className="border-b border-[#F0F0F0] px-5 pb-6 pt-5 md:px-8 md:pb-7 md:pt-6">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <h1 className="text-[1.35rem] font-semibold tracking-[-0.03em] text-primary md:text-[1.5rem]">Give All You Need</h1>
                <div className="relative w-full md:max-w-[360px]">
                  <div className="flex items-center gap-3 rounded-full border border-[#E7E7E7] bg-white px-4 py-2.5">
                    <Icon icon="lucide:search" className="h-4 w-4 text-text-muted" />
                    <input
                      value={searchKeyword}
                      onChange={(event) => setSearchKeyword(event.target.value)}
                      placeholder="搜索商品"
                      className="w-full bg-transparent text-sm text-primary outline-none placeholder:text-text-muted"
                    />
                    <button type="button" className="min-w-[86px] rounded-[999px] bg-primary px-5 py-2 text-xs font-semibold text-white">
                      搜索
                    </button>
                  </div>

                  {suggestions.length > 0 ? (
                    <div className="absolute left-0 right-0 top-[calc(100%+12px)] z-30 rounded-[1.5rem] border border-[#ECECEC] bg-white p-3 shadow-[0_24px_50px_-36px_rgba(17,24,39,0.2)]">
                      {suggestions.map((item) => (
                        <Link
                          key={item.id}
                          to={`/products/${item.id}`}
                          className="flex items-center justify-between rounded-[1.2rem] px-3 py-3 transition-colors hover:bg-[#F7F7F7]"
                        >
                          <span>
                            <span className="block text-sm font-semibold text-primary">{item.name}</span>
                            <span className="block text-xs text-text-muted">{item.categoryLabel}</span>
                          </span>
                          <span className="text-sm font-black text-primary">¥{item.priceLabel}</span>
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="grid gap-8 px-5 py-8 md:px-9 md:py-10 lg:grid-cols-[220px_1fr]">
              <aside className="space-y-5">
                <div>
                  <div className="text-lg font-bold text-primary">商品分类</div>
                  <div className="mt-4 space-y-2">
                    {categoryDefinitions.map((category) => (
                      <button
                        key={category.key}
                        type="button"
                        onClick={() => setActiveCategory(category.key)}
                        className={[
                          'flex w-full items-center justify-between rounded-[1.1rem] px-4 py-3 text-left transition-colors',
                          activeCategory === category.key ? 'bg-[#F4F4F4] text-primary' : 'bg-white text-text-muted hover:bg-[#F7F7F7] hover:text-primary',
                        ].join(' ')}
                      >
                        <span className="flex items-center gap-3 text-sm font-medium">
                          <Icon icon={category.icon} className="h-4 w-4" />
                          {category.label}
                        </span>
                        {activeCategory === category.key ? (
                          <span className="rounded-full bg-accent-red px-2 py-0.5 text-[10px] font-bold text-white">
                            {categoryCounts[category.key] || 0}
                          </span>
                        ) : null}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2 border-t border-[#F0F0F0] pt-4">
                  {quickFilters.map((item) => (
                    <div key={item.key} className="flex items-center gap-3 rounded-[1.1rem] px-4 py-3 text-sm text-primary hover:bg-[#F7F7F7]">
                      <Icon icon={item.icon} className="h-4 w-4" />
                      <span>{item.label}</span>
                    </div>
                  ))}
                </div>
              </aside>

              <div>
                {error ? (
                  <div className="rounded-[1.5rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
                ) : null}

                {loading ? (
                  <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <div key={index} className="h-[360px] animate-pulse rounded-[2rem] bg-[#F6F6F6]" />
                    ))}
                  </div>
                ) : currentPageProducts.length > 0 ? (
                  <>
                    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                      {currentPageProducts.map((product) => (
                        <ProductCard
                          key={product.id}
                          product={product}
                          quickActionLabel="查看详情"
                          quickActionTo={`/products/${product.id}`}
                          primaryActionLabel={session.isAuthenticated ? '立即购买' : '去登录'}
                          primaryActionTo={session.isAuthenticated ? `/flash-sale/${product.id}` : `/auth?redirect=/flash-sale/${product.id}`}
                        />
                      ))}
                    </div>
                    <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
                  </>
                ) : (
                  <div className="rounded-[1.75rem] bg-[#F7F7F7] px-5 py-12 text-center text-sm text-text-muted">
                    没有找到符合当前筛选条件的商品，请更换关键字或分类。
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="dream-shell space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-text-muted">精选推荐</div>
            <h2 className="mt-2 text-3xl font-black tracking-[-0.05em] text-primary">探索更多灵感好物</h2>
          </div>
          <div className="flex gap-2">
            <button type="button" className="flex h-11 w-11 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary">
              <Icon icon="lucide:arrow-left" className="h-4 w-4" />
            </button>
            <button type="button" className="flex h-11 w-11 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary">
              <Icon icon="lucide:arrow-right" className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {recommendedProducts.map((product) => (
            <ProductCard
              key={`recommend-${product.id}`}
              product={product}
              compact
              quickActionLabel="查看详情"
              quickActionTo={`/products/${product.id}`}
              primaryActionLabel="立即购买"
              primaryActionTo={session.isAuthenticated ? `/flash-sale/${product.id}` : `/auth?redirect=/flash-sale/${product.id}`}
            />
          ))}
        </div>
      </section>
    </section>
  );
}
