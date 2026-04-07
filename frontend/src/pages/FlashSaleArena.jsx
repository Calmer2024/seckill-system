import React, { useEffect, useRef, useState } from 'react';
import { orderApi } from '../services/orderApi';

const PRODUCT_ID = 1;

const FlashSaleArena = () => {
  const product = {
    id: PRODUCT_ID,
    name: "Adudu Cleaner Pro",
    tagline: "Redis 预扣库存 + Kafka 异步下单的真实秒杀链路。",
    price: "19.90",
    image: "🤖"
  };

  const [timeLeft, setTimeLeft] = useState(5);
  const [status, setStatus] = useState('locked');
  const [message, setMessage] = useState('倒计时结束后可参与秒杀');
  const [orderId, setOrderId] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    }

    if (status === 'locked') {
      setStatus('ready');
      setMessage('秒杀已开始，准备抢购');
    }
  }, [timeLeft, status]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const pollOrderResult = (currentOrderId) => {
    let attempts = 0;
    timerRef.current = setInterval(async () => {
      attempts += 1;

      try {
        const data = await orderApi.getOrder(currentOrderId);

        if (data.status === 'SUCCESS') {
          setStatus('success');
          setMessage(`订单创建成功，订单号 ${currentOrderId}`);
          stopPolling();
          return;
        }

        if (data.status === 'FAILED') {
          setStatus('failed');
          setMessage('订单创建失败，库存已回补，请稍后重试');
          stopPolling();
          return;
        }

        setStatus('processing');
        setMessage(`排队中，订单号 ${currentOrderId}`);
      } catch (error) {
        setStatus('failed');
        setMessage(error?.response?.data?.message || '查询订单结果失败');
        stopPolling();
      }

      if (attempts >= 15) {
        setStatus('processing');
        setMessage(`订单仍在处理中，可稍后通过订单号 ${currentOrderId} 再次查询`);
        stopPolling();
      }
    }, 1500);
  };

  const handlePurchase = async () => {
    if (status !== 'ready') return;

    setStatus('processing');
    setMessage('请求已提交，正在进入 Kafka 队列');

    try {
      const data = await orderApi.createSeckillOrder(product.id);
      setOrderId(data.order_id);
      setMessage(`请求已排队，订单号 ${data.order_id}`);
      pollOrderResult(data.order_id);
    } catch (error) {
      const code = error?.response?.status;
      const backendMessage = error?.response?.data?.message;

      if (code === 401) {
        setStatus('failed');
        setMessage('请先登录后再参与秒杀');
        return;
      }

      setStatus('failed');
      setMessage(backendMessage || '秒杀失败，请稍后重试');
    }
  };

  const buttonTextMap = {
    locked: 'Waiting...',
    ready: 'Buy Now',
    processing: 'Processing...',
    success: '✓ Success',
    failed: 'Try Again'
  };

  return (
    <div className="w-full min-h-[calc(100vh-80px)] flex flex-col items-center justify-center px-6">
      <div className="max-w-2xl w-full bg-surface rounded-[2rem] p-10 md:p-16 text-center border border-secondary shadow-soft">
        <span className="bg-accent-red text-white text-xs font-bold px-3 py-1 rounded-full mb-6 inline-block">
          Flash Sale Limited
        </span>

        <div className="text-9xl mb-8 drop-shadow-xl">{product.image}</div>

        <h1 className="text-4xl md:text-5xl font-black text-primary mb-4">
          {product.name}
        </h1>
        <p className="text-text-muted mb-4 font-medium">
          {product.tagline}
        </p>

        <div className="h-24 mb-4 flex items-center justify-center">
          {status === 'locked' ? (
            <div className="text-5xl md:text-7xl font-black text-secondary-dark tracking-tighter tabular-nums">
              00:00:0{timeLeft}
            </div>
          ) : (
            <div className="text-5xl md:text-6xl font-black text-primary tracking-tight">
              ${product.price}
            </div>
          )}
        </div>

        <p className="text-sm text-text-muted min-h-10 mb-6">
          {message}
          {orderId ? `，当前订单号：${orderId}` : ''}
        </p>

        <button
          onClick={handlePurchase}
          disabled={status === 'locked' || status === 'processing' || status === 'success'}
          className={`
            w-full md:w-auto px-12 py-4 rounded-full font-bold text-lg transition-all duration-300
            ${status === 'locked' ? 'bg-secondary-dark text-white cursor-not-allowed' : ''}
            ${status === 'ready' ? 'bg-primary text-white hover:bg-primary-light shadow-card-hover cursor-pointer' : ''}
            ${status === 'processing' ? 'bg-text-muted text-white cursor-wait' : ''}
            ${status === 'success' ? 'bg-green-600 text-white cursor-default' : ''}
            ${status === 'failed' ? 'bg-accent-red text-white cursor-pointer hover:opacity-90' : ''}
          `}
        >
          {buttonTextMap[status]}
        </button>
      </div>
    </div>
  );
};

export default FlashSaleArena;
