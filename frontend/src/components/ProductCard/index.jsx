import React, { useState } from 'react';
import { motion } from 'framer-motion';

const ProductCard = ({ product, onBuy }) => {
  const [status, setStatus] = useState('idle'); // idle | loading | success

  const handleBuyClick = async (e) => {
    e.stopPropagation();
    if (status !== 'idle') return;

    setStatus('loading');
    try {
      // 调用父组件传入的购买逻辑
      const success = await onBuy(product.id);
      if (success) {
        setStatus('success');
        setTimeout(() => setStatus('idle'), 2000);
      } else {
        setStatus('idle');
      }
    } catch (error) {
      setStatus('idle');
    }
  };

  return (
    <motion.div
      whileHover={{ y: -6 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      // 使用大圆角、固定比例或最小高度来还原参考图比例
      className="relative w-full h-[480px] rounded-[2.5rem] overflow-hidden cursor-pointer group break-inside-avoid shadow-lg hover:shadow-2xl"
    >
      {/* 1. 背景图片 (使用商品图) */}
      <img 
        src={product.imageUrl || "https://images.unsplash.com/photo-1519681393784-d120267933ba"} 
        alt={product.name}
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
      />

      {/* 2. 底部深色渐变遮罩 (保证文字清晰度) */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#0f171a] via-[#0f171a]/60 to-transparent opacity-90" />

      {/* 3. 卡片内容区 (Flex 布局沉底) */}
      <div className="absolute inset-0 p-6 flex flex-col justify-end">
        
        {/* 标题与价格行 */}
        <div className="flex justify-between items-end mb-3">
          <h3 className="text-2xl font-bold text-white tracking-wide">
            {product.name}
          </h3>
          <div className="bg-white/20 backdrop-blur-md border border-white/10 text-white px-3 py-1 rounded-full text-sm font-medium">
            ¥{product.price}
          </div>
        </div>

        {/* 描述文本 */}
        <p className="text-gray-300 text-sm leading-relaxed mb-5 line-clamp-2">
          {product.desc}
        </p>

        {/* 标签行 (精选、库存) */}
        <div className="flex flex-wrap gap-2 mb-6">
          {product.isTopPick && (
            <span className="bg-white/10 backdrop-blur-md border border-white/5 text-gray-200 px-3 py-1.5 rounded-full text-xs font-medium">
              精选推荐
            </span>
          )}
          {product.stock && (
            <span className="bg-white/10 backdrop-blur-md border border-white/5 text-gray-200 px-3 py-1.5 rounded-full text-xs font-medium">
              仅剩 {product.stock} 件
            </span>
          )}
        </div>

        {/* 加入购物车按钮 */}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleBuyClick}
          disabled={status !== 'idle'}
          className={`w-full py-4 rounded-full text-base font-bold transition-all duration-300 ${
            status === 'success' 
              ? 'bg-green-500 text-white' 
              : 'bg-white text-gray-900 hover:bg-gray-100'
          }`}
        >
          {status === 'idle' && '加入购物车'}
          {status === 'loading' && '处理中...'}
          {status === 'success' && '已添加'}
        </motion.button>
      </div>
    </motion.div>
  );
};

export default ProductCard;