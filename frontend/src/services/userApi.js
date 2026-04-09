import http from '../utils/http';

export const userApi = {
  register: (payload) => {
    return http.post('/api/users/register', payload);
  },

  login: (payload) => {
    return http.post('/api/users/login', payload);
  },
};
