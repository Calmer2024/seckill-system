import { Icon } from '@iconify/react';
import React, { startTransition, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { inventoryApi } from '../services/inventoryApi';
import { orderApi } from '../services/orderApi';
import { productApi } from '../services/productApi';
import { decorateProduct } from '../utils/catalog';

const statusTextMap = {
  PENDING_INVENTORY: '库存确认中',
  CREATED: '待支付',
  PAYING: '支付处理中',
  PAID: '已支付',
  FAILED: '处理失败',
};

function formatPrice(value) {
  return Number(value || 0).toFixed(2);
}

export default function FlashSaleArena({ session }) {
  const { productId: routeProductId } = useParams();
  const navigate = useNavigate();
  const timerRef = useRef(null);
  const productId = Number(routeProductId || 1);

  const [product, setProduct] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [paying, setPaying] = useState(false);
  const [message, setMessage] = useState('准备就绪，可以立即参与本场抢购。');

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const refreshInventory = useEffectEvent(async () => {
    try {
      const inventoryResponse = await inventoryApi.getProductInventory(productId);
      startTransition(() => {
        setInventory(inventoryResponse);
      });
    } catch {
      // 静默刷新失败时保持当前库存显示，避免影响正在进行的下单流程。
    }
  });

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      setLoading(true);
      try {
        const [productResponse, inventoryResponse] = await Promise.all([
          productApi.getProductDetail(productId),
          inventoryApi.getProductInventory(productId),
        ]);
        if (!active) {
          return;
        }
        startTransition(() => {
          setProduct(decorateProduct(productResponse, 0));
          setInventory(inventoryResponse);
        });
        setMessage('商品信息已经准备完成，可以开始参与抢购。');
      } catch (requestError) {
        if (active) {
          setMessage(requestError?.response?.data?.message || '商品或库存信息加载失败。');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadDetail();
    return () => {
      active = false;
      stopPolling();
    };
  }, [productId]);

  useEffect(() => {
    const timer = setInterval(() => {
      refreshInventory();
    }, 2500);

    return () => {
      clearInterval(timer);
    };
  }, [productId]);

  const pollOrder = (orderId) => {
    stopPolling();
    let attempts = 0;

    timerRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const detail = await orderApi.getOrder(orderId);
        startTransition(() => {
          setOrder(detail);
        });
        refreshInventory();

        if (detail.status === 'FAILED') {
          setMessage(detail.failure_reason || '订单处理失败，请稍后再试。');
          stopPolling();
          return;
        }

        if (detail.status === 'CREATED') {
          setMessage('订单已经创建成功，可以继续支付。');
          stopPolling();
          return;
        }

        if (detail.status === 'PAID') {
          setMessage('支付完成，订单状态已更新为已支付。');
          stopPolling();
          return;
        }

        setMessage(`订单处理中，当前状态：${statusTextMap[detail.status] || detail.status}`);
      } catch (requestError) {
        setMessage(requestError?.response?.data?.message || '查询订单状态失败。');
        stopPolling();
      }

      if (attempts >= 18) {
        setMessage('轮询已暂停，请前往订单中心继续查看最新状态。');
        stopPolling();
      }
    }, 1500);
  };

  const handleSeckill = async () => {
    if (!session.isAuthenticated) {
      navigate(`/auth?redirect=/flash-sale/${productId}`);
      return;
    }

    setRequesting(true);
    setMessage('抢购请求已提交，正在为你锁定商品。');

    try {
      const response = await orderApi.createSeckillOrder(productId);
      startTransition(() => {
        setOrder({
          order_id: response.order_id,
          status: response.status,
          product_id: productId,
          quantity: 1,
          total_amount: product?.price ?? 0,
        });
      });
      setMessage(response.message || `订单 ${response.order_id} 已提交。`);
      refreshInventory();
      pollOrder(response.order_id);
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '抢购失败，请稍后重试。');
    } finally {
      setRequesting(false);
    }
  };

  const handlePay = async () => {
    if (!order?.order_id) {
      return;
    }

    setPaying(true);
    setMessage('支付请求已发送，请稍候查看最新状态。');

    try {
      const response = await orderApi.payOrder(order.order_id);
      setMessage(response.message || '支付请求已受理。');
      refreshInventory();
      pollOrder(order.order_id);
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '订单支付失败，请稍后重试。');
    } finally {
      setPaying(false);
    }
  };

  const stockCards = useMemo(() => {
    if (!inventory) {
      return [];
    }

    return [
      { label: '可售库存', value: inventory.available_stock, note: '仍可下单' },
      { label: '等待出库', value: inventory.reserved_stock, note: '处理中' },
      { label: '已售数量', value: inventory.sold_stock, note: '已成交' },
    ];
  }, [inventory]);

  const storyCards = [
    {
      title: '商品简介',
      description: product?.description || '正在整理这件商品的详细介绍、适用场景和选购建议。',
    },
    {
      title: '推荐标签',
      description: product?.tags?.length ? product.tags.join(' · ') : '支持展示商品标签，帮助用户更快了解商品特性。',
    },
  ];

  return (
    <section className="bg-white pt-28 md:pt-32">
      <div className="dream-shell">
        <nav aria-label="面包屑导航" className="mb-6 flex items-center gap-2 text-xs text-[#6e6e73]">
          <Link to="/" className="hover:text-[#0066cc]">商店</Link><Icon icon="lucide:chevron-right" className="h-3 w-3" /><span>{product?.categoryLabel || '商品详情'}</span>
        </nav>
        <section className="border-b border-[#e5e5e7] pb-14">
          <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-center lg:gap-16">
            <div className="max-w-[570px]">
              <div className="text-sm font-semibold text-[#bf4800]">{product?.categoryLabel || '精选商品'}</div>
              <h1 className="mt-3 text-[clamp(2.7rem,5vw,4.6rem)] font-semibold leading-[1.12] tracking-[-0.055em] text-[#1d1d1f]">
                {loading ? '正在准备商品信息...' : product?.name || '商品信息加载失败'}
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-[#6e6e73]">
                {product?.description || '正在整理这件商品的详细介绍、库存变化和订单进度。'}
              </p>

              <div className="mt-5 flex flex-wrap items-center gap-5 text-sm text-[#6e6e73]">
                <span className="inline-flex items-center gap-2">
                  <Icon icon="lucide:star" className="h-4 w-4 text-accent-yellow" />
                  <span className="font-semibold text-primary">{product?.rating || '--'}</span>
                  <span>{product?.reviewsLabel || '0 条评价'}</span>
                </span>
                <span>{product?.highlight || '精选好物'}</span>
              </div>

              {product?.tags?.length ? (
                <div className="mt-5 flex flex-wrap gap-2">
                  {product.tags.map((tag) => (
                    <span
                      key={tag}
                    className="rounded-full bg-[#f5f5f7] px-3 py-1.5 text-xs text-[#6e6e73]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}

              <div className="mt-9 border-t border-[#e5e5e7] pt-7">
                <div>
                  <div className="text-sm text-[#6e6e73]">秒杀价</div>
                  <div className="mt-1 text-[clamp(2.4rem,4vw,3.4rem)] font-semibold tracking-[-0.055em] text-[#1d1d1f] tabular-nums">
                    ¥{product ? formatPrice(product.price) : '--'}
                  </div>
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={handleSeckill}
                  disabled={loading || requesting || paying}
                  className="dream-button-primary min-w-[160px] py-3 disabled:opacity-60"
                >
                  {requesting ? '正在提交...' : '立即购买'}
                </button>
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={!order?.order_id || !['CREATED', 'PAYING'].includes(order?.status) || paying}
                  className="dream-button-secondary min-w-[160px] py-3 disabled:opacity-50"
                >
                  {paying ? '支付处理中...' : '支付当前订单'}
                </button>
              </div>

              <p role="status" className="mt-5 max-w-2xl text-sm leading-7 text-[#6e6e73]">{message}</p>
            </div>

            <div className="relative aspect-square min-h-[340px] overflow-hidden rounded-[2rem] bg-[#f5f5f7]">
              {product ? (
                <img src={product.imageUrl} alt={product.name} className="product-detail-image h-full w-full object-cover" />
              ) : (
                <div className="h-full animate-pulse bg-[#f5f5f7]" />
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-8 border-b border-[#e5e5e7] py-12 md:grid-cols-3 md:gap-0">
          {stockCards.map((item, index) => (
            <div
              key={item.label}
              className={[
                'py-2',
                index > 0 ? 'md:border-l md:border-[#e5e5e7] md:pl-8 lg:pl-10' : 'md:pr-8 lg:pr-10',
              ].join(' ')}
            >
              <div className="text-sm text-[#6e6e73]">{item.label}</div>
              <div className="mt-3 text-[2.7rem] font-semibold tracking-[-0.05em] text-[#1d1d1f] tabular-nums">{item.value}</div>
              <div className="mt-3 text-sm leading-7 text-text-muted">{item.note}</div>
            </div>
          ))}
        </section>

        <section className="grid gap-12 border-b border-[#e5e5e7] py-16 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <div className="text-sm font-semibold text-[#bf4800]">订单进度</div>
            <div className="mt-4 text-[clamp(2.2rem,5vw,3.5rem)] font-semibold leading-[1.15] tracking-[-0.05em] text-[#1d1d1f]">
              {order ? statusTextMap[order.status] || order.status : '等待创建订单'}
            </div>
            <p className="mt-6 max-w-xl text-base leading-8 text-text-muted">{message}</p>
          </div>

          <div className="border-y border-[#e5e5e7]">
            {order ? (
              <>
                <div className="grid gap-3 border-b border-[#e5e5e7] py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-sm text-[#6e6e73]">订单号</div>
                  <div className="break-all text-base font-semibold text-primary">{order.order_id}</div>
                </div>
                <div className="grid gap-3 border-b border-[#e5e5e7] py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-sm text-[#6e6e73]">订单状态</div>
                  <div className="text-base font-semibold text-primary">{statusTextMap[order.status] || order.status}</div>
                </div>
                <div className="grid gap-3 py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-sm text-[#6e6e73]">订单金额</div>
                  <div className="text-base font-semibold text-primary">¥{formatPrice(order.total_amount)}</div>
                </div>
              </>
            ) : (
              <div className="py-6 text-sm leading-8 text-text-muted">
                下单成功后，这里会按顺序展示你的订单编号、当前状态与支付金额，信息会随着轮询结果自动刷新。
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-10 py-16 lg:grid-cols-2">
          {storyCards.map((item, index) => (
            <article
              key={item.title}
              className={[
                'border-t border-[#e5e5e7] pt-8',
                index % 2 === 1 ? 'lg:pl-10' : '',
              ].join(' ')}
            >
              <div className="text-sm font-semibold text-[#bf4800]">了解更多</div>
              <div className="mt-4 text-[1.9rem] font-semibold tracking-[-0.05em] text-[#1d1d1f]">{item.title}</div>
              <p className="mt-5 max-w-xl text-sm leading-8 text-text-muted">{item.description}</p>
            </article>
          ))}
        </section>
      </div>
    </section>
  );
}
