import { Icon } from '@iconify/react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
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
        setProduct(decorateProduct(productResponse, 0));
        setInventory(inventoryResponse);
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

  const pollOrder = (orderId) => {
    stopPolling();
    let attempts = 0;

    timerRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const detail = await orderApi.getOrder(orderId);
        setOrder(detail);

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
      setOrder({
        order_id: response.order_id,
        status: response.status,
        product_id: productId,
        quantity: 1,
        total_amount: product?.price ?? 0,
      });
      setMessage(response.message || `订单 ${response.order_id} 已提交。`);
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
      title: '更清爽的陈列方式',
      description: '以更少的边框和更大的留白，让信息自然流动，阅读体验更接近精品零售陈列页。',
    },
    {
      title: '更直接的购买路径',
      description: '价格、库存、订单和支付集中在同一页完成，避免在多个模块之间来回切换。',
    },
  ];

  return (
    <section className="bg-white pt-28 md:pt-32">
      <div className="dream-shell">
        <section className="border-b border-[#EEEEEE] pb-16">
          <div className="grid gap-12 lg:grid-cols-[1.02fr_0.98fr] lg:items-center">
            <div className="max-w-[640px]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-text-muted">Dreamstore Detail</div>
              <h1 className="mt-6 text-[clamp(3rem,7vw,5.8rem)] font-black leading-[0.9] tracking-[-0.08em] text-primary">
                {loading ? '正在准备商品信息...' : product?.name || '商品信息加载失败'}
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-text-muted">
                在更纯净的白底陈列页里查看商品信息、库存变化和订单进度，让浏览、下单与支付保持在同一条阅读动线上。
              </p>

              <div className="mt-10 flex flex-wrap items-end gap-x-12 gap-y-6">
                <div>
                  <div className="text-xs uppercase tracking-[0.22em] text-text-muted">当前价格</div>
                  <div className="mt-3 text-6xl font-black tracking-[-0.07em] text-primary">
                    ¥{product ? formatPrice(product.price) : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.22em] text-text-muted">当前账号</div>
                  <div className="mt-3 text-lg font-semibold text-primary">
                    {session.isAuthenticated ? session.username : '尚未登录'}
                  </div>
                </div>
              </div>

              <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={handleSeckill}
                  disabled={loading || requesting || paying}
                  className="dream-button-primary min-w-[180px] py-4 disabled:opacity-60"
                >
                  {requesting ? '正在提交...' : '立即购买'}
                </button>
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={!order?.order_id || !['CREATED', 'PAYING'].includes(order?.status) || paying}
                  className="dream-button-secondary min-w-[180px] py-4 disabled:opacity-50"
                >
                  {paying ? '支付处理中...' : '支付当前订单'}
                </button>
                <Link to="/" className="dream-button-secondary py-4">
                  返回首页
                </Link>
              </div>

              <p className="mt-8 max-w-2xl text-sm leading-8 text-text-muted">{message}</p>
            </div>

            <div className="relative min-h-[520px] overflow-hidden rounded-[3rem] border border-[#F1F1F1] bg-white">
              <div className="absolute inset-x-[10%] top-[12%] h-14 rounded-full bg-[#F5F5F5] blur-3xl" />
              <div className="absolute right-[10%] top-[18%] h-32 w-32 rounded-full bg-[#F8F8F8] blur-3xl" />
              <div className="absolute bottom-[12%] left-1/2 h-12 w-[56%] -translate-x-1/2 rounded-full bg-black/6 blur-2xl" />

              {product ? (
                <div className="relative flex h-full min-h-[520px] flex-col justify-between p-8 md:p-10">
                  <div className="text-right text-[11px] font-semibold uppercase tracking-[0.24em] text-text-muted">
                    {product.categoryLabel}
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <div className="flex h-[250px] w-[250px] items-center justify-center rounded-[34%] border border-[#F0F0F0] bg-[linear-gradient(180deg,#FFFFFF_0%,#F8F8F8_100%)] shadow-[0_40px_90px_-44px_rgba(17,24,39,0.28)] md:h-[300px] md:w-[300px]">
                      <Icon icon={product.visualIcon || 'lucide:package-open'} className="h-28 w-28 text-primary md:h-32 md:w-32" />
                    </div>
                  </div>
                  <div className="flex items-end justify-between gap-6 border-t border-[#F0F0F0] pt-6">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-text-muted">标签</div>
                      <div className="mt-2 text-base font-semibold text-primary">{product.categoryBadge}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-text-muted">亮点</div>
                      <div className="mt-2 text-base font-semibold text-primary">{product.highlight}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-[520px] animate-pulse bg-[#F7F7F7]" />
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-8 border-b border-[#EEEEEE] py-12 md:grid-cols-3 md:gap-0">
          {stockCards.map((item, index) => (
            <div
              key={item.label}
              className={[
                'py-2',
                index > 0 ? 'md:border-l md:border-[#EEEEEE] md:pl-8 lg:pl-10' : 'md:pr-8 lg:pr-10',
              ].join(' ')}
            >
              <div className="text-xs uppercase tracking-[0.24em] text-text-muted">{item.label}</div>
              <div className="mt-4 text-5xl font-black tracking-[-0.06em] text-primary">{item.value}</div>
              <div className="mt-3 text-sm leading-7 text-text-muted">{item.note}</div>
            </div>
          ))}
        </section>

        <section className="grid gap-12 border-b border-[#EEEEEE] py-16 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-text-muted">Order Progress</div>
            <div className="mt-5 text-[clamp(2.2rem,5vw,4.2rem)] font-black leading-[0.96] tracking-[-0.06em] text-primary">
              {order ? statusTextMap[order.status] || order.status : '等待创建订单'}
            </div>
            <p className="mt-6 max-w-xl text-base leading-8 text-text-muted">{message}</p>
          </div>

          <div className="border-y border-[#EEEEEE]">
            {order ? (
              <>
                <div className="grid gap-3 border-b border-[#EEEEEE] py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-xs font-semibold uppercase tracking-[0.22em] text-text-muted">订单号</div>
                  <div className="break-all text-base font-semibold text-primary">{order.order_id}</div>
                </div>
                <div className="grid gap-3 border-b border-[#EEEEEE] py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-xs font-semibold uppercase tracking-[0.22em] text-text-muted">订单状态</div>
                  <div className="text-base font-semibold text-primary">{statusTextMap[order.status] || order.status}</div>
                </div>
                <div className="grid gap-3 py-6 md:grid-cols-[120px_1fr]">
                  <div className="text-xs font-semibold uppercase tracking-[0.22em] text-text-muted">订单金额</div>
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
                'border-t border-[#EEEEEE] pt-8',
                index % 2 === 1 ? 'lg:pl-10' : '',
              ].join(' ')}
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.26em] text-text-muted">Design Note</div>
              <div className="mt-4 text-[1.9rem] font-black tracking-[-0.05em] text-primary">{item.title}</div>
              <p className="mt-5 max-w-xl text-sm leading-8 text-text-muted">{item.description}</p>
            </article>
          ))}
        </section>
      </div>
    </section>
  );
}
