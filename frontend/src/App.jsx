import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Icon } from '@iconify/react'; // 引入 Iconify
import StoreFront from './pages/StoreFront';
import FlashSaleArena from './pages/FlashSaleArena';
// import AuthPortal from './pages/AuthPortal'; // 暂缺按需引入

const Layout = ({ children }) => {
  return (
    // 添加统一的中文字体栈，并将背景设为 relative，以便容纳绝对定位的导航栏
    <div className="relative min-h-screen w-full bg-background flex flex-col font-['PingFang_SC','Microsoft_YaHei','sans-serif']">
      
      {/* 悬浮卡片式的顶部导航栏 */}
      {/* pointer-events-none 避免外层容器遮挡下方的点击事件，内部 nav 再开启 auto */}
      <div className="absolute top-6 left-0 right-0 z-50 px-4 md:px-8 flex justify-center pointer-events-none">
        <nav className="w-full max-w-[1400px] bg-white/95 backdrop-blur-md rounded-full px-8 py-4 flex items-center justify-between shadow-sm pointer-events-auto">
          
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2">
            <Icon icon="lucide:triangle-right" className="w-7 h-7 text-primary -rotate-90" />
            <span className="font-black text-xl text-primary tracking-tight">DreamStore</span>
          </Link>

          {/* 中间菜单 - 中文化并调整间距 */}
          <div className="hidden md:flex items-center space-x-10">
            <Link to="/" className="text-text-muted hover:text-primary transition-colors text-sm font-bold">首页</Link>
            {/* 当前高亮的菜单 */}
            <Link to="/" className="text-primary transition-colors text-sm font-bold">商城</Link>
            <Link to="/detail" className="text-text-muted hover:text-primary transition-colors text-sm font-bold">秒杀</Link>
            <Link to="/" className="text-text-muted hover:text-primary transition-colors text-sm font-bold">博客</Link>
          </div>

          {/* 右侧图标区 - 替换为 Iconify */}
          <div className="flex items-center space-x-6">
            <button className="text-text-main hover:text-primary transition-colors">
              <Icon icon="lucide:search" className="w-5 h-5" />
            </button>
            <button className="text-text-main hover:text-primary transition-colors relative">
              <Icon icon="lucide:shopping-cart" className="w-5 h-5" />
              <span className="absolute -top-1.5 -right-2 bg-accent-red text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center border-2 border-white">2</span>
            </button>
            {/* 头像 */}
            <div className="w-9 h-9 rounded-full bg-secondary overflow-hidden cursor-pointer hover:ring-2 ring-primary/20 transition-all">
              <img src="https://i.pravatar.cc/100" alt="Avatar" className="w-full h-full object-cover" />
            </div>
          </div>
          
        </nav>
      </div>

      {/* 页面内容区 */}
      <main className="flex-1 w-full">
        {children}
      </main>
      
    </div>
  );
};

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<StoreFront />} />
          <Route path="/detail" element={<FlashSaleArena />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;