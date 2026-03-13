import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

const AuthPortal = () => {
  const [isLoginMode, setIsLoginMode] = useState(true); // 控制当前是登录还是注册模式
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState(''); // 用于注册成功的提示
  
  const navigate = useNavigate();

  // 核心提交逻辑：同时处理登录和注册
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsAuthenticating(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      // 动态判断调用哪个后端接口
      const endpoint = isLoginMode ? '/api/users/login' : '/api/users/register';
      
      const response = await fetch(`http://127.0.0.1:8001${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        if (isLoginMode) {
          // 登录成功：保存 Token 并跳转到商店首页
          localStorage.setItem('access_token', data.access_token);
          navigate('/'); 
        } else {
          // 注册成功：给出反馈，并平滑切换回登录模式
          setSuccessMsg('账号创建成功，正在为您跳转至登录...');
          setTimeout(() => {
            setIsLoginMode(true);
            setSuccessMsg('');
            setPassword(''); // 出于安全习惯，清空密码框
            setIsAuthenticating(false);
          }, 1500);
          return; // 提前 return，防止走到 finally 里面重置 isAuthenticating
        }
      } else {
        // 【架构级细节】处理 FastAPI 不同的报错格式
        if (response.status === 422) {
          // Pydantic 的校验错误 (detail 是一个数组)
          setErrorMsg('输入格式有误，请确保密码至少6位。');
        } else {
          // 业务逻辑错误 (如用户名已存在、密码错误，detail 是一段文本)
          setErrorMsg(data.detail || '身份验证失败，请重试。');
        }
      }
    } catch (error) {
      setErrorMsg('无法连接到服务器，请检查网络或后端服务是否开启。');
    } finally {
      setIsAuthenticating(false);
    }
  };

  return (
    <div className="w-full min-h-screen flex items-center justify-center px-4 relative">
      <motion.div 
        className="w-full max-w-md z-10"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
      >
        {/* Titanium Glass 毛玻璃卡片 */}
        <div className="bg-apple-card backdrop-blur-2xl border border-white/60 rounded-[2rem] p-10 md:p-12 shadow-apple">
          
          <div className="text-center mb-10">
            <h1 className="text-3xl font-display font-semibold text-apple-dark mb-3 tracking-tight">
              {isLoginMode ? '登录你的账户' : '创建新账户'}
            </h1>
            <p className="text-gray-500 font-body text-sm">
              {isLoginMode ? '输入你的账号以访问 Midnight Store。' : '加入我们，体验极简的数字购物之旅。'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col space-y-5">
            {/* 极简输入框组 */}
            <div className="space-y-4">
              <div>
                <input 
                  type="text" 
                  placeholder="用户名 (最少3位字符)" 
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-white/50 border border-gray-200/50 rounded-2xl px-5 py-4 text-apple-dark outline-none focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500/30 transition-all duration-300 font-body placeholder:text-gray-400"
                />
              </div>
              <div>
                <input 
                  type="password" 
                  placeholder="密码 (最少6位字符)" 
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-white/50 border border-gray-200/50 rounded-2xl px-5 py-4 text-apple-dark outline-none focus:bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500/30 transition-all duration-300 font-body placeholder:text-gray-400"
                />
              </div>
            </div>

            {/* 状态信息展示：错误或成功提示 */}
            <AnimatePresence mode="wait">
              {errorMsg && (
                <motion.div 
                  key="error"
                  initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
                  className="text-red-500 text-sm font-body text-center"
                >
                  {errorMsg}
                </motion.div>
              )}
              {successMsg && (
                <motion.div 
                  key="success"
                  initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
                  className="text-green-600 text-sm font-body text-center"
                >
                  {successMsg}
                </motion.div>
              )}
            </AnimatePresence>

            {/* 主操作按钮 */}
            <motion.button 
              type="submit"
              disabled={isAuthenticating}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full mt-4 py-4 bg-apple-dark text-white font-body font-medium rounded-full shadow-sm hover:shadow-md transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isAuthenticating ? (
                <span className="flex items-center justify-center space-x-2">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>处理中...</span>
                </span>
              ) : (isLoginMode ? '继续' : '立即注册')}
            </motion.button>
          </form>

          {/* 模式切换按钮 */}
          <div className="mt-8 text-center border-t border-gray-200/50 pt-6">
            <button 
              type="button"
              onClick={() => {
                setIsLoginMode(!isLoginMode);
                setErrorMsg(''); // 切换时清空报错
                setSuccessMsg('');
              }}
              className="text-apple-blue text-sm hover:underline font-body transition-colors"
            >
              {isLoginMode ? '没有账户？立即创建一个' : '已有账户？返回登录'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default AuthPortal;