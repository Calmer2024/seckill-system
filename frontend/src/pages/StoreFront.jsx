import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { productApi } from '../services/api';

const StoreFront = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  // 前端独立调用 Mock 接口
  useEffect(() => {
    productApi.getProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  const handleBuy = async (id, e) => {
    e.stopPropagation(); // 阻止事件冒泡
    const btn = e.currentTarget;
    const originalText = btn.innerText;
    btn.innerText = "处理中...";
    
    // 调用 Mock 购买接口
    const res = await productApi.buyProduct(id);
    if (res.success) {
      btn.innerText = "已添加";
      btn.classList.add("bg-green-600", "text-white");
      setTimeout(() => {
        btn.innerText = originalText;
        btn.classList.remove("bg-green-600", "text-white");
      }, 2000);
    }
  };

  return (
    <div className="w-full min-h-screen px-6 py-24 md:px-12 lg:px-24">
      {/* 头部标题区：Apple 式巨大字体与留白 */}
      <motion.div 
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="max-w-7xl mx-auto mb-16"
      >
        <h1 className="text-5xl md:text-7xl font-display font-bold tracking-tight text-apple-dark mb-4">
          选购最新产品。
        </h1>
        <h2 className="text-2xl md:text-3xl font-display text-gray-500 tracking-tight">
          你喜欢的设计，<br className="md:hidden" />现在一览无余。
        </h2>
      </motion.div>

      {/* 加载骨架屏 */}
      {loading && (
        <div className="max-w-7xl mx-auto flex space-x-4">
          <div className="w-full h-64 bg-black/5 rounded-[2rem] animate-pulse"></div>
        </div>
      )}

      {/* 瀑布流容器 (Masonry Layout) 
          使用 CSS columns 实现错落有致的瀑布流，break-inside-avoid 保证卡片不被截断 */}
      <div className="max-w-7xl mx-auto columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
        {products.map((product, index) => (
          <motion.div
            key={product.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: index * 0.1 }}
            className="break-inside-avoid"
          >
            {/* 商品卡片：分层透明 (Glassmorphism) + 戏剧性悬停阴影 */}
            <motion.div 
              whileHover={{ scale: 1.01, y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="relative overflow-hidden bg-apple-card backdrop-blur-2xl border border-white/60 shadow-apple hover:shadow-apple-hover rounded-[2rem] p-8 cursor-pointer flex flex-col justify-between"
              style={{ minHeight: product.height === 'h-96' ? '24rem' : product.height === 'h-80' ? '20rem' : '16rem' }}
            >
              {/* 装饰性背景色块 (模拟产品图) */}
              <div className={`absolute inset-0 opacity-40 ${product.imgColor} -z-10`} />

              {/* 顶部标签 */}
              <div className="flex justify-between items-start mb-8">
                {product.tag && (
                  <span className="text-xs font-bold uppercase tracking-widest text-orange-600 bg-orange-100/50 px-3 py-1 rounded-full backdrop-blur-md border border-orange-200/50">
                    {product.tag}
                  </span>
                )}
              </div>

              {/* 商品信息 */}
              <div className="mt-auto">
                <h3 className="text-2xl font-display font-semibold mb-2">{product.name}</h3>
                <p className="text-gray-500 font-body mb-6">{product.desc}</p>
                
                <div className="flex justify-between items-center">
                  <span className="text-lg font-medium">RMB {product.price}</span>
                  {/* Apple 经典胶囊按钮 */}
                  <motion.button 
                    whileTap={{ scale: 0.95 }}
                    onClick={(e) => handleBuy(product.id, e)}
                    className="bg-apple-dark text-white px-5 py-2 rounded-full text-sm font-medium hover:bg-gray-800 transition-colors shadow-sm"
                  >
                    购买
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default StoreFront;