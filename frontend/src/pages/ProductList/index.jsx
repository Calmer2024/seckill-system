import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { productApi } from '../../services/api';
import ProductCard from '../../components/ProductCard'; // 引入拆分出的组件

const StoreFront = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 模拟获取包含新字段的数据
    productApi.getProducts().then(data => {
      // 假设后端返回的数据缺少某些 UI 字段，这里可以做一层适配
      const adaptedData = data.map(p => ({
        ...p,
        // 如果后端没返回图片，给个占位图适配新 UI
        imageUrl: p.imageUrl || "https://images.unsplash.com/photo-1519681393784-d120267933ba",
        isTopPick: p.tag === 'Top Pick' || Math.random() > 0.5, 
        stock: Math.floor(Math.random() * 10) + 1, 
      }));
      setProducts(adaptedData);
      setLoading(false);
    });
  }, []);

  // 将购买逻辑作为回调传递给子组件
  const handleBuy = async (id) => {
    const res = await productApi.buyProduct(id);
    return res.success; // 返回布尔值让组件自己处理 UI 变化
  };

  return (
    <div className="w-full min-h-screen bg-gray-50 px-6 py-24 md:px-12 lg:px-24">
      {/* 头部标题区 */}
      <motion.div 
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="max-w-7xl mx-auto mb-16"
      >
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-gray-900 mb-4">
          探索美学边界。
        </h1>
        <h2 className="text-2xl md:text-3xl text-gray-500 tracking-tight">
          你喜欢的设计，<br className="md:hidden" />现在一览无余。
        </h2>
      </motion.div>

      {/* 加载骨架屏 */}
      {loading && (
        <div className="max-w-7xl mx-auto columns-1 md:columns-2 lg:columns-3 gap-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="w-full h-[480px] bg-gray-200 rounded-[2.5rem] animate-pulse mb-6"></div>
          ))}
        </div>
      )}

      {/* 瀑布流容器 */}
      <div className="max-w-7xl mx-auto columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
        {products.map((product, index) => (
          <motion.div
            key={product.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: index * 0.1 }}
          >
            {/* 注入商品数据和购买回调 */}
            <ProductCard product={product} onBuy={handleBuy} />
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default StoreFront;