import http from '../utils/http';

export const productApi = {
  getProducts: (params = {}) => {
    return http.get('/api/products', { params });
  },

  getProductDetail: (id) => {
    return http.get(`/api/products/${id}`);
  },

  searchProducts: (keyword, limit = 8) => {
    return http.get('/api/products/search', {
      params: { keyword, limit },
    });
  },

  prewarmCache: () => {
    return http.post('/api/products/prewarm');
  },
};
