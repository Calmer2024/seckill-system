//在这里我们将基础 URL 动态绑定到环境变量，做到不同环境自动适配
import axios from 'axios';

// 1. 创建统一的 axios 实例
const http = axios.create({
  // 动态读取环境变量中的基础 URL
  baseURL: import.meta.env.VITE_API_BASE_URL, 
  timeout: 10000, // 设置 10 秒超时
  headers: {
    'Content-Type': 'application/json',
  }
});

// 2. 请求拦截器 (可以在这里统一携带 Token)
http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 3. 响应拦截器 (统一处理错误码，解耦组件错误处理逻辑)
http.interceptors.response.use(
  (response) => {
    // 假设后端返回的数据都在 response.data 中
    return response.data;
  },
  (error) => {
    // 统一错误处理逻辑，例如 401 自动跳转登录页，500 弹出全局错误提示
    if (error.response) {
      switch (error.response.status) {
        case 401:
          console.error("未授权，请重新登录");
          break;
        case 404:
          console.error("请求的接口不存在");
          break;
        case 500:
          console.error("服务器内部错误");
          break;
        default:
          console.error(`请求错误: ${error.response.status}`);
      }
    } else if (error.request) {
      console.error("网络连接失败，请检查网络");
    }
    return Promise.reject(error);
  }
);

export default http;
