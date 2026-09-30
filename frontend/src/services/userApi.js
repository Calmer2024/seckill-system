import http from '../utils/http';

export const userApi = {
  register: (payload) => {
    return http.post('/api/users/register', payload);
  },

  login: (payload) => {
    return http.post('/api/users/login', payload);
  },

  getProfile: () => {
    return http.get('/api/users/profile');
  },

  updateProfile: (payload) => {
    return http.put('/api/users/profile', payload);
  },

  uploadAvatar: (file) => {
    const form = new FormData();
    form.append('file', file);
    return http.post('/api/users/profile/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};
