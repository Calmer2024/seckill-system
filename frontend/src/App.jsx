import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import StoreFront from './pages/StoreFront';
import AuthPortal from './pages/AuthPortal';
import FlashSaleArena from './pages/FlashSaleArena';

// Apple 风格底层环境光布局
const AppleLayout = ({ children }) => {
  return (
    <div className="relative min-h-screen w-full overflow-hidden">
      <div className="ambient-background"></div>
      <div className="titanium-noise"></div>
      
      {/* 极简毛玻璃顶部导航栏 */}
      <nav className="fixed top-0 w-full h-[52px] bg-apple-card backdrop-blur-md border-b border-white/40 z-50 flex items-center justify-center space-x-8 px-6">
        <Link to="/" className="font-display font-medium text-xs tracking-widest text-apple-dark hover:text-black transition-colors">STORE</Link>
        <Link to="/detail" className="font-display font-medium text-xs tracking-widest text-apple-dark hover:text-black transition-colors">VISION PRO</Link>
        <Link to="/login" className="font-display font-medium text-xs tracking-widest text-apple-dark hover:text-black transition-colors">ACCOUNT</Link>
      </nav>

      <main className="relative z-10 w-full pt-[52px]">
        {children}
      </main>
    </div>
  );
};

function App() {
  return (
    <Router>
      <AppleLayout>
        <Routes>
          <Route path="/" element={<StoreFront />} />
          <Route path="/login" element={<AuthPortal />} />
          <Route path="/detail" element={<FlashSaleArena />} />
        </Routes>
      </AppleLayout>
    </Router>
  );
}

export default App;