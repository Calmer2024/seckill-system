import { Icon } from '@iconify/react';
import React, { startTransition, useEffect, useEffectEvent, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { orderApi } from '../services/orderApi';

const statusTextMap = {
  PENDING_INVENTORY: '库存确认中',
  CREATED: '待支付',
  PAYING: '支付处理中',
  PAID: '已支付',
  FAILED: '处理失败',
};

function formatAmount(value) {
  return Number(value || 0).toFixed(2);
}

export default function OrdersCenter({ session }) {
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');
  const [payingOrderId, setPayingOrderId] = useState(null);

  const loadOrders = useEffectEvent(async ({ silent = false } = {}) => {
    if (!session.isAuthenticated) {
      startTransition(() => {
        setOrders([]);
        setLoading(false);
        setSyncing(false);
      });
      return;
    }

    if (silent) {
      setSyncing(true);
    } else {
      setLoading(true);
    }

    try {
      const response = await orderApi.getMyOrders();
      const nextOrders = Array.isArray(response) ? response : [response];
      startTransition(() => {
        setOrders(nextOrders);
      });
      setMessage('');
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '订单列表加载失败，请稍后再试。');
    } finally {
      if (silent) {
        setSyncing(false);
      } else {
        setLoading(false);
      }
    }
  });

  useEffect(() => {
    loadOrders({ silent: false });
  }, [session.isAuthenticated]);

  useEffect(() => {
    if (!session.isAuthenticated) {
      return undefined;
    }

    const timer = setInterval(() => {
      loadOrders({ silent: true });
    }, 5000);

    return () => clearInterval(timer);
  }, [session.isAuthenticated]);

  const metrics = useMemo(() => {
    return [
      { label: '全部订单', value: orders.length },
      { label: '待处理', value: orders.filter((item) => ['PENDING_INVENTORY', 'CREATED', 'PAYING'].includes(item.status)).length },
      { label: '已支付', value: orders.filter((item) => item.status === 'PAID').length },
    ];
  }, [orders]);

  const handlePay = async (order) => {
      setPayingOrderId(order.order_id);
      setMessage('支付请求已发送，请稍候查看最新状态。');

    try {
      const response = await orderApi.payOrder(order.order_id);
      setMessage(response.message || '支付请求已受理。');
      await loadOrders({ silent: true });
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '支付失败，请稍后重试。');
    } finally {
      setPayingOrderId(null);
    }
  };

  if (!session.isAuthenticated) {
    return (
      <section className="dream-shell pb-20 pt-32 md:pt-40">
        <div className="mx-auto max-w-[640px] text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#f5f5f7] text-[#6e6e73]"><Icon icon="lucide:package" className="h-7 w-7" /></div>
          <h1 className="mt-7 text-[clamp(2.5rem,5vw,4rem)] font-semibold leading-tight tracking-[-0.055em] text-[#1d1d1f]">查看你的订单。</h1>
          <p className="mx-auto mt-4 max-w-md text-base leading-8 text-[#6e6e73]">登录后即可查看订单进度、支付状态，并继续完成待支付订单。</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3"><Link to="/auth?redirect=/orders" className="dream-button-primary">前往登录</Link><Link to="/" className="dream-button-secondary">继续选购</Link></div>
        </div>
      </section>
    );
  }

  return (
    <section className="dream-shell space-y-7 pb-20 pt-28 md:pt-32">
      <section className="border-b border-[#e5e5e7] pb-9">
        <p className="text-sm font-semibold text-[#bf4800]">你的商店</p>
        <div className="mt-2 flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div><h1 className="text-[clamp(2.6rem,5vw,4.3rem)] font-semibold leading-tight tracking-[-0.055em] text-[#1d1d1f]">订单。</h1><p className="mt-3 text-sm leading-7 text-[#6e6e73]">查看每笔购买的进度与支付状态。订单会自动更新。</p></div>
          <div className="flex gap-8 md:pb-2">{metrics.map((item) => <div key={item.label}><p className="text-[1.7rem] font-semibold tracking-[-0.05em] text-[#1d1d1f] tabular-nums">{item.value}</p><p className="text-xs text-[#6e6e73]">{item.label}</p></div>)}</div>
        </div>
      </section>

      {message ? (
        <div role="status" className="rounded-2xl bg-[#f5f5f7] px-5 py-4 text-sm text-[#1d1d1f]">{message}</div>
      ) : null}

      {syncing && !loading ? (
        <div className="text-right text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">订单状态同步中</div>
      ) : null}

      {loading ? (
        <div className="grid gap-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-40 animate-pulse rounded-[1.6rem] bg-[#f5f5f7]" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-[1.8rem] bg-[#f5f5f7] px-6 py-16 text-center">
          <div className="text-[1.8rem] font-semibold tracking-[-0.045em] text-[#1d1d1f]">还没有订单。</div>
          <p className="mt-3 text-sm leading-7 text-text-muted">
            去商品页挑选一件喜欢的商品，下单成功后这里会自动出现你的订单。
          </p>
          <div className="mt-8">
            <button type="button" onClick={() => navigate('/')} className="dream-button-primary">
              浏览商品
            </button>
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          {orders.map((order) => (
            <article key={order.order_id} className="rounded-[1.8rem] bg-[#f5f5f7] p-6 md:p-8">
              <div className="flex flex-col justify-between gap-5 border-b border-black/10 pb-6 sm:flex-row sm:items-start">
                <div><p className="text-xs font-medium text-[#6e6e73]">订单号 {order.order_id}</p><h2 className="mt-2 text-[1.45rem] font-semibold tracking-[-0.035em] text-[#1d1d1f]">商品 #{order.product_id}</h2></div>
                <span className={`w-fit rounded-full px-3 py-1.5 text-xs font-semibold ${order.status === 'PAID' ? 'bg-[#e8f5eb] text-[#217a39]' : order.status === 'FAILED' ? 'bg-[#fff0ef] text-[#b42318]' : 'bg-white text-[#6e6e73]'}`}>{statusTextMap[order.status] || order.status}</span>
              </div>
              <div className="flex flex-col justify-between gap-5 pt-6 sm:flex-row sm:items-end">
                <div><p className="text-xs text-[#6e6e73]">订单金额</p><p className="mt-1 text-[1.8rem] font-semibold tracking-[-0.05em] text-[#1d1d1f] tabular-nums">¥{formatAmount(order.total_amount)}</p></div>
                <div className="flex flex-wrap gap-3">
                  <Link to={`/products/${order.product_id}`} className="dream-button-secondary">查看商品</Link>
                  {['CREATED', 'PAYING'].includes(order.status) ? <button
                    type="button"
                    onClick={() => handlePay(order)}
                    disabled={payingOrderId === order.order_id}
                    className="dream-button-primary disabled:opacity-50"
                  >
                    {payingOrderId === order.order_id ? '支付处理中...' : '支付订单'}
                  </button> : null}
                </div>
              </div>

              {order.failure_reason ? (
                <div className="mt-4 rounded-[1.4rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                  失败原因：{order.failure_reason}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
