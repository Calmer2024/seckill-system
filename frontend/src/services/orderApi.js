import http from '../utils/http';

export const orderApi = {
  createSeckillOrder: (productId) => {
    return http.post('/api/orders/seckill', {
      product_id: productId,
      quantity: 1,
    });
  },

  getOrder: (orderId) => {
    return http.get(`/api/orders/${orderId}`);
  },

  getMyOrders: () => {
    return http.get('/api/orders');
  },

  payOrder: (orderId, amount) => {
    const payload = amount ? { amount } : {};
    return http.post(`/api/orders/${orderId}/pay`, payload);
  },
};
