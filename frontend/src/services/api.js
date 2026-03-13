// src/services/api.js

// 模拟不同高度的商品数据，以完美展现瀑布流 (Masonry) 效果
const MOCK_PRODUCTS = [
  { id: 1, name: "iPhone 16 Pro", desc: "钛金属，坚固轻盈。", price: 7999, tag: "新款", height: "h-96", imgColor: "bg-gradient-to-br from-gray-200 to-gray-400" },
  { id: 2, name: "MacBook Air M3", desc: "轻如羽毛，重磅实力。", price: 8999, tag: "", height: "h-64", imgColor: "bg-gradient-to-br from-blue-100 to-blue-200" },
  { id: 3, name: "Apple Watch Ultra 2", desc: "冒险，再跨一步。", price: 6499, tag: "极光款", height: "h-80", imgColor: "bg-gradient-to-br from-orange-100 to-orange-200" },
  { id: 4, name: "AirPods Pro", desc: "沉浸式降噪。", price: 1899, tag: "", height: "h-56", imgColor: "bg-gradient-to-br from-gray-50 to-gray-200" },
  { id: 5, name: "iPad Pro", desc: "薄出超能力。", price: 8999, tag: "M4芯片", height: "h-80", imgColor: "bg-gradient-to-br from-purple-100 to-purple-200" },
  { id: 6, name: "Vision Pro", desc: "欢迎来到空间计算时代。", price: 29999, tag: "限量", height: "h-96", imgColor: "bg-gradient-to-br from-slate-200 to-slate-400" },
];

export const productApi = {
  // 模拟网络延迟获取商品列表
  getProducts: () => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(MOCK_PRODUCTS);
      }, 600); // 模拟 0.6 秒网络延迟
    });
  },
  
  // 预留的下单接口，供前端独立测试交互
  buyProduct: (id) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, message: `商品 ${id} 抢购成功` });
      }, 400);
    });
  }
};