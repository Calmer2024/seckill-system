import React, { useState, useEffect } from 'react';

const FlashSaleArena = () => {
  const product = { name: "Adudu Cleaner Pro", tagline: "更强劲的吸力，更优雅的设计。", price: "19.90", image: "🤖" };
  const [timeLeft, setTimeLeft] = useState(5);
  const [status, setStatus] = useState('locked'); // 'locked' | 'ready' | 'processing' | 'success'

  useEffect(() => {
    if (timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else if (timeLeft === 0 && status === 'locked') {
      setStatus('ready');
    }
  }, [timeLeft, status]);

  const handlePurchase = () => {
    if (status !== 'ready') return;
    setStatus('processing');
    setTimeout(() => setStatus('success'), 1500);
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
        <p className="text-text-muted mb-8 font-medium">
          {product.tagline}
        </p>

        {/* 倒计时或价格展示 */}
        <div className="h-24 mb-8 flex items-center justify-center">
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

        {/* 按钮状态 */}
        <button
          onClick={handlePurchase}
          disabled={status === 'locked' || status === 'processing' || status === 'success'}
          className={`
            w-full md:w-auto px-12 py-4 rounded-full font-bold text-lg transition-all duration-300
            ${status === 'locked' ? 'bg-secondary-dark text-white cursor-not-allowed' : ''}
            ${status === 'ready' ? 'bg-primary text-white hover:bg-primary-light shadow-card-hover cursor-pointer' : ''}
            ${status === 'processing' ? 'bg-text-muted text-white cursor-wait' : ''}
            ${status === 'success' ? 'bg-green-600 text-white cursor-default' : ''}
          `}
        >
          {status === 'locked' && 'Waiting...'}
          {status === 'ready' && 'Buy Now'}
          {status === 'processing' && 'Processing...'}
          {status === 'success' && '✓ Success'}
        </button>

      </div>
    </div>
  );
};

export default FlashSaleArena;