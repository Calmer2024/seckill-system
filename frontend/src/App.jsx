import { Icon } from '@iconify/react';
import React, { useEffect, useState } from 'react';
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';

import { useAuthSession } from './hooks/useAuthSession';
import AuthPortal from './pages/AuthPortal';
import FlashSaleArena from './pages/FlashSaleArena';
import OrdersCenter from './pages/OrdersCenter';
import StoreFront from './pages/StoreFront';

const navItems = [
  { to: '/', label: '首页', end: true },
  { to: '/flash-sale/1', label: '商店' },
  { to: '/orders', label: '订单' },
];

function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary">
        <Icon icon="lucide:gem" className="h-4 w-4" />
      </div>
      <div className="dream-brand text-[1.65rem] font-bold leading-none text-primary">Dreamstore</div>
    </div>
  );
}

function Header({ session, onLogout }) {
  return (
    <header className="absolute inset-x-0 top-0 z-50">
      <div className="dream-shell">
        <div className="rounded-b-[1.8rem] border-x border-b border-[#ECECEC] bg-white px-5 py-4 shadow-[0_14px_30px_-24px_rgba(17,24,39,0.16)] md:px-7">
          <div className="flex items-center justify-between gap-4">
            <Link to="/">
              <BrandMark />
            </Link>

            <nav className="hidden items-center gap-7 lg:flex">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    [
                      'text-sm font-medium transition-colors',
                      isActive ? 'text-primary' : 'text-text-muted hover:text-primary',
                    ].join(' ')
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <div className="flex items-center gap-2 md:gap-3">
              <button
                type="button"
                className="flex h-10 w-10 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary"
                aria-label="搜索"
              >
                <Icon icon="lucide:search" className="h-4 w-4" />
              </button>

              <Link
                to="/orders"
                className="relative flex h-10 w-10 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary"
                aria-label="购物车"
              >
                <Icon icon="lucide:shopping-cart" className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-red" />
              </Link>

              {session.isAuthenticated ? (
                <button
                  type="button"
                  onClick={onLogout}
                  title="退出登录"
                  className="overflow-hidden rounded-full border border-[#EAEAEA] bg-white"
                >
                  <img src="/avatar.JPG" alt="用户头像" className="h-10 w-10 object-cover" />
                </button>
              ) : (
                <Link
                  to="/auth"
                  className="overflow-hidden rounded-full border border-[#EAEAEA] bg-white"
                  aria-label="用户中心"
                >
                  <img src="/avatar.JPG" alt="用户头像" className="h-10 w-10 object-cover" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="px-4 pb-12 pt-20 md:px-6">
      <div className="dream-shell-wide space-y-8">
        <section className="overflow-hidden rounded-[2.7rem] bg-primary px-7 py-12 text-white md:px-14 md:py-16">
          <div className="grid gap-8 lg:grid-cols-[1fr_0.8fr] lg:items-end">
            <div>
              <div className="text-[clamp(2.2rem,5vw,4rem)] font-black leading-[1.28] tracking-[0.08em]">
                准备好发现
                <br />
                新一季好物了吗？
              </div>
              <div className="mt-7 flex max-w-[330px] items-center gap-2 rounded-full border border-white/10 bg-white/8 p-2">
                <input
                  className="w-full bg-transparent px-3 text-sm text-white outline-none placeholder:text-white/55"
                  placeholder="输入你的邮箱"
                />
                <button type="button" className="min-w-[92px] rounded-[999px] bg-white px-6 py-2.5 text-sm font-semibold text-primary">
                  发送
                </button>
              </div>
            </div>

            <div className="space-y-3 text-sm leading-7 text-white/72">
              <div className="text-xs uppercase tracking-[0.24em] text-white/45">Dreamstore</div>
              <p>为居家、影音与个护场景精选日常好物，让你在简洁清爽的商城里完成浏览、下单与付款。</p>
            </div>
          </div>
        </section>

        <section className="dream-panel rounded-[2.7rem] px-7 py-10 md:px-14 md:py-12">
          <div className="grid gap-8 lg:grid-cols-[1.2fr_repeat(3,0.7fr)]">
            <div>
              <BrandMark />
              <p className="mt-4 max-w-md text-sm leading-7 text-text-muted">
                Dreamstore 为你整理值得购买的热门商品、日常用品与精选好物，让购物体验更轻松直接。
              </p>
            </div>

            <div>
              <div className="text-sm font-bold text-primary">关于我们</div>
              <div className="mt-4 space-y-3 text-sm text-text-muted">
                <div>品牌故事</div>
                <div>团队介绍</div>
                <div>联系方式</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-bold text-primary">服务支持</div>
              <div className="mt-4 space-y-3 text-sm text-text-muted">
                <div>订单查询</div>
                <div>配送政策</div>
                <div>常见问题</div>
              </div>
            </div>

            <div>
              <div className="text-sm font-bold text-primary">社交媒体</div>
              <div className="mt-4 flex gap-3">
                {['lucide:twitter', 'lucide:facebook', 'lucide:linkedin', 'lucide:instagram'].map((icon) => (
                  <div
                    key={icon}
                    className="flex h-11 w-11 items-center justify-center rounded-full border border-[#EAEAEA] bg-white text-primary"
                  >
                    <Icon icon={icon} className="h-4 w-4" />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-col gap-3 border-t border-[#EFEFEF] pt-5 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
            <div>Copyright © 2026 Dreamstore. All rights reserved.</div>
            <div className="flex gap-5">
              <span>服务条款</span>
              <span>隐私政策</span>
            </div>
          </div>
        </section>
      </div>
    </footer>
  );
}

function ScrollToTop() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.pathname, location.search]);

  return null;
}

function Layout({ session, onLogout, children }) {
  const location = useLocation();
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => {
    if (!session.isAuthenticated) {
      return;
    }

    const pendingToast = sessionStorage.getItem('dreamstore_login_success');
    if (!pendingToast) {
      return;
    }

    setToastMessage(pendingToast);
    sessionStorage.removeItem('dreamstore_login_success');
  }, [location.pathname, session.isAuthenticated]);

  useEffect(() => {
    if (!toastMessage) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setToastMessage('');
    }, 2200);

    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  return (
    <div className="min-h-screen pb-4">
      <ScrollToTop />
      <Header session={session} onLogout={onLogout} />
      {toastMessage ? (
        <div className="fixed right-4 top-24 z-[70] md:right-6">
          <div className="flex items-center gap-3 rounded-[1.4rem] border border-[#DDEBDD] bg-white px-4 py-3 shadow-[0_20px_42px_-32px_rgba(17,24,39,0.28)]">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#EDF7ED] text-[#2F6B3B]">
              <Icon icon="lucide:check" className="h-4 w-4" />
            </span>
            <div>
              <div className="text-sm font-semibold text-primary">登录成功</div>
              <div className="text-xs text-text-muted">{toastMessage}</div>
            </div>
          </div>
        </div>
      ) : null}
      <main>{children}</main>
      <Footer />
    </div>
  );
}

export default function App() {
  const { session, logout } = useAuthSession();

  return (
    <BrowserRouter>
      <Layout session={session} onLogout={logout}>
        <Routes>
          <Route path="/" element={<StoreFront session={session} />} />
          <Route path="/auth" element={<AuthPortal session={session} />} />
          <Route path="/products/:productId" element={<FlashSaleArena session={session} />} />
          <Route path="/flash-sale/:productId" element={<FlashSaleArena session={session} />} />
          <Route path="/detail" element={<FlashSaleArena session={session} />} />
          <Route path="/orders" element={<OrdersCenter session={session} />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
