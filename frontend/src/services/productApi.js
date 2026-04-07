import http from '../utils/http';

export const productApi = {
  /**
   * 获取所有商品列表
   * @returns {Promise} 返回商品数组
   */
  getProducts: () => {
    return http.get('/api/products');
  },

  /**
   * 获取单个商品详情
   * @param {number} id 商品 ID
   * @returns {Promise} 返回单个商品对象
   */
  getProductDetail: (id) => {
    return http.get(`/api/products/${id}`);
  },

  /**
   * 触发商品缓存预热 (通常为管理员操作)
   */
  prewarmCache: () => {
    return http.post('/api/products/prewarm');
  }
};