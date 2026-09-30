import { Icon } from '@iconify/react';
import React, { useEffect, useRef, useState } from 'react';
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

function formatJoinDate(value) {
  if (!value) {
    return '刚刚加入';
  }

  try {
    return new Date(value).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return '刚刚加入';
  }
}

function UserAvatarControl({ session, onLogout, onUploadAvatar }) {
  const [open, setOpen] = useState(false);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState('');
  const fileInputRef = useRef(null);
  const activeAvatar = session.avatarUrl;

  const handleAvatarUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }

    setAvatarError('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
      setAvatarError('请选择不超过 2 MB 的 JPG、PNG 或 WebP 图片。');
      return;
    }

    setSavingAvatar(true);
    try {
      await onUploadAvatar(file);
    } catch (error) {
      setAvatarError(error?.response?.data?.detail || '上传失败，请重试。');
    } finally {
      setSavingAvatar(false);
    }
  };

  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {session.isAuthenticated ? (
        <button
          type="button"
          className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#EAEAEA] bg-white text-primary shadow-[0_12px_28px_-24px_rgba(17,24,39,0.28)]"
          aria-label="用户资料"
        >
          {activeAvatar ? <img src={activeAvatar} alt="用户头像" className="h-full w-full object-cover" /> : <Icon icon="lucide:user-round" className="h-5 w-5" />}
        </button>
      ) : (
        <Link
          to="/auth"
          className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[#EAEAEA] bg-white text-primary shadow-[0_12px_28px_-24px_rgba(17,24,39,0.28)]"
          aria-label="用户中心"
        >
          <Icon icon="lucide:user-round" className="h-5 w-5" />
        </Link>
      )}

      {open ? (
        <div className="absolute right-0 top-[calc(100%+14px)] z-[80] w-[320px] rounded-[1.8rem] border border-[#ECECEC] bg-white p-4 shadow-[0_26px_56px_-36px_rgba(17,24,39,0.3)]">
          <div aria-hidden="true" className="absolute -inset-x-px -top-[15px] h-[16px]" />
          {session.isAuthenticated ? (
            <>
              <div className="flex items-start gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#F5F5F5] text-primary">
                  {activeAvatar ? <img src={activeAvatar} alt="当前头像" className="h-full w-full object-cover" /> : <Icon icon="lucide:user-round" className="h-8 w-8" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-text-muted">Dreamstore Member</div>
                  <div className="mt-2 truncate text-lg font-black tracking-[-0.04em] text-primary">{session.username}</div>
                  <div className="mt-2 grid grid-cols-2 gap-3 text-xs leading-6 text-text-muted">
                    <div>
                      <div className="uppercase tracking-[0.18em]">用户 ID</div>
                      <div className="text-sm font-semibold text-primary">{session.userId}</div>
                    </div>
                    <div>
                      <div className="uppercase tracking-[0.18em]">加入时间</div>
                      <div className="text-sm font-semibold text-primary">{formatJoinDate(session.createdAt)}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-[1.4rem] bg-[#FAFAFA] p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">个人头像</div>
                <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleAvatarUpload} aria-label="上传头像图片" />
                <button type="button" disabled={savingAvatar} onClick={() => fileInputRef.current?.click()} className="dream-button-secondary mt-3 w-full gap-2 disabled:cursor-not-allowed disabled:opacity-60">
                  <Icon icon="lucide:upload" className="h-4 w-4" />
                  {savingAvatar ? '上传中…' : activeAvatar ? '更换头像' : '上传头像'}
                </button>
                <div className="mt-2 text-xs leading-5 text-text-muted">支持 JPG、PNG、WebP，文件不超过 2 MB。</div>
                {avatarError ? <div role="alert" className="mt-2 text-xs text-red-600">{avatarError}</div> : null}
              </div>

              <div className="mt-4 flex gap-2">
                <Link to="/orders" className="dream-button-secondary flex-1">
                  我的订单
                </Link>
                <button type="button" onClick={onLogout} className="dream-button-primary flex-1">
                  退出登录
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[#F5F5F5] text-primary">
                  <Icon icon="lucide:user-round" className="h-8 w-8" />
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-text-muted">Guest</div>
                  <div className="mt-2 text-lg font-black tracking-[-0.04em] text-primary">登录后开启个人资料</div>
                  <div className="mt-2 text-sm leading-6 text-text-muted">
                    登录后可以设置头像、查看订单，并在顶部悬浮卡片里快速访问你的账户信息。
                  </div>
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <Link to="/auth" className="dream-button-primary flex-1">
                  前往登录
                </Link>
                <Link to="/" className="dream-button-secondary flex-1">
                  返回首页
                </Link>
              </div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

function Header({ session, onLogout, onUploadAvatar }) {
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

              <UserAvatarControl session={session} onLogout={onLogout} onUploadAvatar={onUploadAvatar} />
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

function Layout({ session, onLogout, onUploadAvatar, children }) {
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
      <Header session={session} onLogout={onLogout} onUploadAvatar={onUploadAvatar} />
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
      <main key={location.pathname} className="page-enter">{children}</main>
      <Footer />
    </div>
  );
}

export default function App() {
  const { session, logout, uploadAvatar } = useAuthSession();

  return (
    <BrowserRouter>
      <Layout session={session} onLogout={logout} onUploadAvatar={uploadAvatar}>
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
