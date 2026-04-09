import http from '../utils/http';

export const inventoryApi = {
  getProductInventory: (productId) => {
    return http.get(`/api/inventory/products/${productId}`);
  },
};
