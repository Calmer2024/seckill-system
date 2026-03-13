import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const FlashSaleArena = () => {
  // Mock 数据
  const product = { name: "Vision Pro", tagline: "欢迎来到空间计算时代。", price: "29,999" };
  const [timeLeft, setTimeLeft] = useState(5); // 5秒倒计时
  const [status, setStatus] = useState('locked'); // 'locked' | 'ready' | 'processing' | 'success'

  // 独立倒计时逻辑
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
    
    // 【前端独立 Mock 测试】模拟抢购请求
    setTimeout(() => {
      setStatus('success');
    }, 1500);
  };

  return (
    <div className="w-full min-h-screen flex flex-col items-center justify-center px-6 relative">
      
      {/* 背景巨型隐约的光晕 (模拟舞台灯光) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] bg-gray-200 rounded-full blur-[100px] opacity-30 pointer-events-none -z-10"></div>

      <motion.div 
        className="text-center max-w-4xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <span className="text-orange-600 font-semibold tracking-widest text-sm uppercase mb-6 block">
          限量发售即将开启
        </span>
        <h1 className="text-6xl md:text-8xl font-display font-bold tracking-tighter text-apple-dark mb-6">
          {product.name}
        </h1>
        <p className="text-2xl md:text-3xl font-display text-gray-500 tracking-tight mb-16">
          {product.tagline}
        </p>

        {/* 极简优雅倒计时 */}
        <div className="mb-16">
          <AnimatePresence mode="popLayout">
            {status === 'locked' ? (
              <motion.div 
                key="timer"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.1 }}
                className="text-7xl md:text-9xl font-display font-medium text-gray-300 tracking-tighter"
              >
                00:00:0{timeLeft}
              </motion.div>
            ) : (
              <motion.div 
                key="price"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-5xl md:text-6xl font-display font-semibold text-apple-dark tracking-tight"
              >
                RMB {product.price}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* 购买动作区：从锁定状态平滑过渡到可操作状态 */}
        <motion.div layout className="flex justify-center">
          <button
            onClick={handlePurchase}
            disabled={status === 'locked' || status === 'processing' || status === 'success'}
            className={`
              relative px-12 py-5 rounded-full font-body font-medium text-lg transition-all duration-500 shadow-sm
              ${status === 'locked' ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : ''}
              ${status === 'ready' ? 'bg-apple-dark text-white hover:bg-gray-800 hover:shadow-apple-hover hover:-translate-y-1 cursor-pointer' : ''}
              ${status === 'processing' ? 'bg-gray-800 text-white cursor-wait scale-95' : ''}
              ${status === 'success' ? 'bg-green-600 text-white cursor-default' : ''}
            `}
          >
            {status === 'locked' && '等待开始'}
            {status === 'ready' && '立即抢购'}
            {status === 'processing' && '处理订单中...'}
            {status === 'success' && '✓ 抢购成功'}
          </button>
        </motion.div>

        {/* 成功状态的补充说明 */}
        <AnimatePresence>
          {status === 'success' && (
            <motion.p 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 text-gray-500 font-body text-sm"
            >
              您的订单已确认，稍后将发送详细信息至您的 Apple ID 邮箱。
            </motion.p>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};

export default FlashSaleArena;