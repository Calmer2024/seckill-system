import React, { useState, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { productApi } from '../services/productApi';

const StoreFront = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 9;

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setLoading(true);
        const data = await productApi.getProducts();
        
        const mockIcons = [
          "lucide:smartphone", 
          "lucide:headphones", 
          "lucide:bot", 
          "lucide:camera", 
          "lucide:speaker", 
          "lucide:radio", 
          "lucide:laptop", 
          "lucide:watch", 
          "lucide:lightbulb"
        ];

        const formattedProducts = data.map((item) => ({
          ...item,
          price: Number(item.price).toFixed(2),
          rating: (4.0 + (item.id % 10) * 0.1).toFixed(1),
          reviews: `${100 + (item.id * 23)}`,
          tag: item.id % 2 === 0 ? "热门" : "推荐",
          image: mockIcons[item.id % mockIcons.length] 
        }));

        setProducts(formattedProducts);
      } catch (error) {
        console.error("UI层捕获到获取商品失败:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  const totalPages = Math.ceil(products.length / itemsPerPage) || 1;
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentProducts = products.slice(startIndex, startIndex + itemsPerPage);

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 300, behavior: 'smooth' }); 
  };

  const handlePrevious = () => {
    if (currentPage > 1) handlePageChange(currentPage - 1);
  };

  const handleNext = () => {
    if (currentPage < totalPages) handlePageChange(currentPage + 1);
  };

  const pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    // 1. 最外层容器：负责承载顶部清晰的大背景图
    <div 
      className="w-full pb-20 font-['PingFang_SC','Microsoft_YaHei','sans-serif'] bg-top bg-no-repeat bg-[length:100%_450px]"
      style={{ backgroundImage: "url('/store_bg.jpg')" }}
    >
      
      {/* 2. 背景中的巨大文本，z-index 较低 (z-0)，会被下方的白色区域遮盖 */}
      <div className="relative w-full h-[340px] max-w-[1400px] mx-auto flex items-end justify-center overflow-hidden">
        {/* 使用 translate-y 将文字往下沉，制造被切割的视觉 */}
        <h1 className="text-[280px] font-black text-white mix-blend-normal opacity-100 select-none tracking-tighter leading-none translate-y-16 z-0">
          Shop
        </h1>
      </div>

      {/* 3. 覆盖在背景图上的主体内容卡片 */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-8">
        
        {/* 白色的“盖板”容器，带有大圆角，制造出卡片叠加的层次感 */}
        <div className="bg-background rounded-t-[3rem] px-8 pt-10 pb-8 shadow-sm">
          
          {/* 顶部标题与搜索 */}
          <div className="flex flex-col md:flex-row justify-between items-center mb-12 border-b border-secondary pb-6">
            <h2 className="text-3xl font-bold text-primary">为您提供所需的一切</h2>
            <div className="relative mt-4 md:mt-0 flex items-center w-full md:w-96">
              <Icon icon="lucide:search" className="w-4 h-4 absolute left-4 text-text-muted" />
              <input 
                type="text" 
                placeholder="在 DreamStore 中搜索" 
                className="w-full bg-surface py-3 pl-12 pr-24 rounded-full text-sm outline-none border border-transparent focus:border-secondary-dark transition-colors"
              />
              <button className="absolute right-1.5 top-1.5 bottom-1.5 bg-primary text-white px-6 rounded-full text-xs font-bold hover:bg-primary-light transition-colors">
                搜索
              </button>
            </div>
          </div>

          {/* 主体两栏布局 */}
          <div className="flex flex-col lg:flex-row gap-12">
            
            {/* 左侧边栏 - 分类导航 */}
            <aside className="w-full lg:w-64 flex-shrink-0">
              <h3 className="font-bold text-lg mb-6">商品分类</h3>
              <ul className="space-y-4 text-sm font-medium">
                <li className="flex items-center justify-between text-primary bg-surface p-3 rounded-xl border border-secondary-light">
                  <span className="flex items-center gap-3">
                    <Icon icon="lucide:package" className="text-xl" /> 全部商品
                  </span>
                  <span className="bg-accent-red text-white text-[10px] px-2.5 py-1 rounded-full font-bold">{products.length}</span>
                </li>
                <li className="flex items-center text-text-muted hover:text-primary cursor-pointer p-3 transition-colors">
                  <Icon icon="lucide:home" className="mr-3 text-xl" /> 居家生活
                </li>
                <li className="flex items-center text-text-muted hover:text-primary cursor-pointer p-3 transition-colors">
                  <Icon icon="lucide:music" className="mr-3 text-xl" /> 影音娱乐
                </li>
                <li className="flex items-center text-text-muted hover:text-primary cursor-pointer p-3 transition-colors">
                  <Icon icon="lucide:smartphone" className="mr-3 text-xl" /> 数码配件
                </li>
                <li className="flex items-center text-text-muted hover:text-primary cursor-pointer p-3 transition-colors">
                  <Icon icon="lucide:archive" className="mr-3 text-xl" /> 收纳整理
                </li>
              </ul>
              
              <div className="mt-10 pt-8 border-t border-secondary space-y-5 text-sm font-medium text-text-muted">
                <div className="flex justify-between items-center cursor-pointer hover:text-primary transition-colors">
                  <span className="flex items-center gap-3"><Icon icon="lucide:badge-plus" className="text-lg" /> 新品上架</span>
                  <Icon icon="lucide:chevron-right" className="w-4 h-4" />
                </div>
                <div className="flex justify-between items-center cursor-pointer hover:text-primary transition-colors">
                  <span className="flex items-center gap-3"><Icon icon="lucide:flame" className="text-lg" /> 热销排行</span>
                  <Icon icon="lucide:chevron-right" className="w-4 h-4" />
                </div>
                <div className="flex justify-between items-center cursor-pointer hover:text-primary transition-colors">
                  <span className="flex items-center gap-3"><Icon icon="lucide:tag" className="text-lg" /> 限时特惠</span>
                  <Icon icon="lucide:chevron-right" className="w-4 h-4" />
                </div>
              </div>
            </aside>

            {/* 右侧商品网格 */}
            <div className="flex-1">
              {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                   {Array.from({ length: 9 }).map((_, i) => <div key={i} className="h-[340px] bg-surface rounded-[2rem] animate-pulse"></div>)}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                  {currentProducts.map((product) => (
                    <div key={product.id} className="group flex flex-col">
                      <div className="relative bg-surface rounded-[2rem] p-8 h-[280px] flex items-center justify-center mb-5 group-hover:shadow-soft transition-shadow">
                        <span className="absolute top-5 right-5 bg-white text-xs font-bold px-4 py-1.5 rounded-full shadow-sm text-text-main">
                          {product.tag}
                        </span>
                        <div className="text-primary drop-shadow-md group-hover:scale-110 transition-transform duration-500 ease-out">
                          <Icon icon={product.image} width="100" height="100" strokeWidth="1.2" />
                        </div>
                      </div>

                      <div className="px-2">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-bold text-lg text-primary truncate pr-2">{product.name}</h4>
                          <span className="font-black text-lg text-primary">¥{product.price}</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-text-muted mb-6">
                          <Icon icon="mdi:star" className="text-accent-yellow text-base" />
                          <span className="text-primary font-bold">{product.rating}</span>
                          <span>({product.reviews} 条评价)</span>
                          <span className="ml-auto opacity-70">库存 {product.stock}</span>
                        </div>

                        <div className="flex gap-3">
                          <button className="flex-1 py-3 rounded-full text-sm font-bold text-primary bg-secondary-light hover:bg-secondary transition-colors border border-transparent">
                            加入购物车
                          </button>
                          <button className="flex-1 py-3 rounded-full text-sm font-bold text-white bg-primary hover:bg-primary-light transition-colors shadow-md shadow-black/10">
                            立即购买
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 动态分页组件 */}
              {totalPages > 1 && (
                <div className="mt-16 flex justify-between items-center text-sm border-t border-secondary pt-8">
                  <button 
                    onClick={handlePrevious}
                    disabled={currentPage === 1}
                    className={`flex items-center gap-2 font-medium ${currentPage === 1 ? 'text-secondary-dark cursor-not-allowed' : 'text-text-muted hover:text-primary transition-colors'}`}
                  >
                    <Icon icon="lucide:arrow-left" className="w-5 h-5" /> 上一页
                  </button>
                  
                  <div className="flex gap-2">
                    {pageNumbers.map(number => (
                      <button 
                        key={number}
                        onClick={() => handlePageChange(number)}
                        className={`w-10 h-10 rounded-xl font-bold transition-all duration-200 ${
                          currentPage === number 
                            ? 'bg-primary text-white shadow-md' 
                            : 'text-text-muted hover:bg-surface hover:text-primary'
                        }`}
                      >
                        {number}
                      </button>
                    ))}
                  </div>

                  <button 
                    onClick={handleNext}
                    disabled={currentPage === totalPages}
                    className={`flex items-center gap-2 font-medium ${currentPage === totalPages ? 'text-secondary-dark cursor-not-allowed' : 'text-text-muted hover:text-primary transition-colors'}`}
                  >
                    下一页 <Icon icon="lucide:arrow-right" className="w-5 h-5" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* 底部 CTA 订阅卡片 */}
          <div className="mt-32 w-full bg-surface-black rounded-[2.5rem] p-12 md:p-20 flex flex-col md:flex-row items-center justify-between shadow-2xl relative overflow-hidden">
             {/* 装饰性光晕 */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-white/5 rounded-full blur-3xl pointer-events-none"></div>
            
            <div className="text-white max-w-lg mb-10 md:mb-0 relative z-10">
              <h2 className="text-4xl md:text-6xl font-black mb-6 leading-tight tracking-tight">准备好探索<br/>最新好物了吗？</h2>
              <div className="flex items-center w-full max-w-md relative mt-10">
                <input 
                  type="email" 
                  placeholder="输入您的邮箱" 
                  className="w-full bg-white text-primary py-4 pl-8 pr-32 rounded-full text-sm outline-none font-medium focus:ring-4 ring-white/20 transition-all"
                />
                <button className="absolute right-1.5 top-1.5 bottom-1.5 bg-primary text-white px-8 rounded-full text-sm font-bold hover:bg-primary-light transition-colors shadow-lg">
                  订阅
                </button>
              </div>
            </div>
            <div className="text-gray-400 text-sm max-w-xs leading-relaxed border-l border-gray-700/50 pl-10 hidden md:block relative z-10">
              <p className="text-white font-bold mb-3 text-base">DreamStore 懂家更懂你</p>
              我们倾听您的需求，为您挑选最合适的生活好物，打造专属的智能生活体验。每一次选择，都是对美好生活的期许。
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StoreFront;