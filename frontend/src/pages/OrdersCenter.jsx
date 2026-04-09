import { Icon } from '@iconify/react';
import React, { useEffect, useMemo, useState } from 'react';
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
  const [message, setMessage] = useState('');
  const [payingOrderId, setPayingOrderId] = useState(null);

  const loadOrders = async () => {
    if (!session.isAuthenticated) {
      setOrders([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await orderApi.getMyOrders();
      setOrders(Array.isArray(response) ? response : [response]);
      setMessage('');
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '订单列表加载失败，请稍后再试。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [session.isAuthenticated]);

  useEffect(() => {
    if (!session.isAuthenticated) {
      return undefined;
    }

    const timer = setInterval(() => {
      loadOrders();
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
      await loadOrders();
    } catch (requestError) {
      setMessage(requestError?.response?.data?.message || '支付失败，请稍后重试。');
    } finally {
      setPayingOrderId(null);
    }
  };

  if (!session.isAuthenticated) {
    return (
      <section className="dream-shell pt-28 md:pt-32">
        <div className="dream-panel grid gap-8 overflow-hidden lg:grid-cols-[1fr_0.95fr]">
          <div className="bg-primary px-6 py-8 text-white md:px-8 md:py-10">
            <div className="dream-kicker text-white/55">Dreamstore 订单中心</div>
            <h1 className="mt-3 text-[clamp(2.6rem,6vw,4.5rem)] font-black leading-[0.94] tracking-[-0.07em]">
              登录之后，
              <br />
              才能查看
              <br />
              你的订单。
            </h1>
            <p className="mt-4 max-w-lg text-sm leading-7 text-white/72">
              登录后你可以查看自己的购物订单、订单状态，并直接完成支付。
            </p>
          </div>

          <div className="flex flex-col justify-center px-6 py-8 md:px-8 md:py-10">
            <div className="rounded-[1.8rem] border border-[#EAEAEA] bg-white p-6">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-white">
                <Icon icon="lucide:lock" className="h-6 w-6" />
              </div>
              <div className="mt-5 text-3xl font-black tracking-[-0.05em] text-primary">订单中心需要先登录</div>
              <p className="mt-3 text-sm leading-7 text-text-muted">
                登录后订单中心会自动展示你的秒杀订单、待支付订单和最新支付状态。
              </p>
            </div>

            <div className="mt-6 flex flex-col gap-3 md:flex-row">
              <Link to="/auth?redirect=/orders" className="dream-button-primary flex-1">
                前往登录
              </Link>
              <Link to="/" className="dream-button-secondary flex-1">
                返回首页
              </Link>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="dream-shell space-y-8 pt-28 md:pt-32">
      <section className="dream-panel overflow-hidden">
        <div className="grid gap-0 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="bg-primary px-6 py-8 text-white md:px-8 md:py-10">
            <div className="dream-kicker text-white/55">订单中心</div>
            <h1 className="mt-3 text-[clamp(2.6rem,6vw,4.5rem)] font-black leading-[0.94] tracking-[-0.07em]">
              统一查看
              <br />
              购物订单与
              <br />
              支付状态。
            </h1>
            <p className="mt-4 max-w-lg text-sm leading-7 text-white/72">
              订单中心会持续刷新最新状态，让你随时查看待付款订单、已支付订单和最新处理结果。
            </p>
          </div>

            <div className="grid gap-4 px-6 py-6 md:grid-cols-3 md:px-8 md:py-8">
              {metrics.map((item) => (
              <div key={item.label} className="rounded-[1.75rem] border border-[#EAEAEA] bg-white p-5">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">{item.label}</div>
                <div className="mt-3 text-4xl font-black tracking-[-0.06em] text-primary">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-[1.6rem] border border-[#E8E2D8] bg-white px-5 py-4 text-sm text-primary">{message}</div>
      ) : null}

      {loading ? (
        <div className="grid gap-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-40 animate-pulse rounded-[2rem] bg-[#F2EEE8]" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <div className="dream-panel px-6 py-12 text-center">
          <div className="text-3xl font-black tracking-[-0.05em] text-primary">还没有秒杀订单</div>
          <p className="mt-3 text-sm leading-7 text-text-muted">
            去商品页挑选一件喜欢的商品，下单成功后这里会自动出现你的订单。
          </p>
          <div className="mt-8">
            <button type="button" onClick={() => navigate('/flash-sale/1')} className="dream-button-primary">
              去秒杀会场
            </button>
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          {orders.map((order) => (
            <article key={order.order_id} className="dream-panel p-5 md:p-6">
              <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
                <div className="grid gap-4 md:grid-cols-4">
                  <div className="dream-subpanel p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">订单号</div>
                    <div className="mt-2 break-all text-sm font-black text-primary">{order.order_id}</div>
                  </div>
                  <div className="dream-subpanel p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">商品 ID</div>
                    <div className="mt-2 text-sm font-black text-primary">{order.product_id}</div>
                  </div>
                  <div className="dream-subpanel p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">订单金额</div>
                    <div className="mt-2 text-sm font-black text-primary">¥{formatAmount(order.total_amount)}</div>
                  </div>
                  <div className="dream-subpanel p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">订单状态</div>
                    <div className="mt-2 text-sm font-black text-primary">{statusTextMap[order.status] || order.status}</div>
                  </div>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <Link to={`/products/${order.product_id}`} className="dream-button-secondary">
                    查看商品
                  </Link>
                  <button
                    type="button"
                    onClick={() => handlePay(order)}
                    disabled={!['CREATED', 'PAYING'].includes(order.status) || payingOrderId === order.order_id}
                    className="dream-button-primary disabled:opacity-50"
                  >
                    {payingOrderId === order.order_id ? '支付处理中...' : '支付订单'}
                  </button>
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
