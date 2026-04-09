import { Icon } from '@iconify/react';
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { userApi } from '../services/userApi';
import { saveAccessToken } from '../utils/auth';

const benefits = [
  {
    icon: 'lucide:shield-check',
    title: '安全登录',
    description: '登录后即可查看订单、继续付款，并安全保存你的购物记录。',
  },
  {
    icon: 'lucide:zap',
    title: '极速秒杀',
    description: '登录后即可直接进入秒杀会场，完成下单、支付与订单追踪。',
  },
  {
    icon: 'lucide:package-open',
    title: '轻松下单',
    description: '从浏览商品到完成支付，整个购物过程都可以在一个页面里顺畅完成。',
  },
];

export default function AuthPortal({ session }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [form, setForm] = useState({ username: '', password: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (session.isAuthenticated) {
      navigate(searchParams.get('redirect') || '/', { replace: true });
    }
  }, [navigate, searchParams, session.isAuthenticated]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setSuccess('');

    try {
      if (isLoginMode) {
        const data = await userApi.login(form);
        saveAccessToken(data.access_token);
        sessionStorage.setItem('dreamstore_login_success', '欢迎回来，已为你打开 Dreamstore。');
        navigate(searchParams.get('redirect') || '/', { replace: true });
      } else {
        await userApi.register(form);
        setSuccess('注册成功，请使用刚创建的账号登录 Dreamstore。');
        setIsLoginMode(true);
        setForm((current) => ({ ...current, password: '' }));
      }
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError('输入格式不符合要求：用户名不少于 3 位，密码不少于 6 位。');
      } else {
        setError(detail || '请求失败，请稍后再试。');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="dream-shell pt-28 md:pt-32">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.02fr]">
        <section className="overflow-hidden rounded-[2.4rem] bg-primary px-6 py-6 text-white md:px-8 md:py-8">
          <div className="dream-pill border-white/10 bg-white/8 text-white/70">Dreamstore 账号中心</div>
          <h1 className="mt-5 text-[clamp(1.95rem,4vw,3.35rem)] font-black leading-[1.34] tracking-[0.1em]">
            登录之后，
            <br />
            选购与订单
            <br />
            一步直达。
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-6 text-white/72 md:text-[15px]">
            登录或注册后，你可以继续收藏喜欢的商品、查看购物订单，并顺畅完成支付流程。
          </p>

          <div className="mt-7 grid gap-3">
            {benefits.map((item) => (
              <div key={item.title} className="rounded-[1.6rem] border border-white/10 bg-white/8 p-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-primary">
                    <Icon icon={item.icon} className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-base font-bold">{item.title}</div>
                    <div className="mt-1.5 text-sm leading-6 text-white/70">{item.description}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="dream-panel p-5 md:p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="dream-kicker">{isLoginMode ? '欢迎回来' : '创建账号'}</div>
              <h2 className="mt-2 text-4xl font-black tracking-[-0.06em] text-primary">
                {isLoginMode ? '登录 Dreamstore' : '注册 Dreamstore'}
              </h2>
            </div>
            <div className="flex h-14 w-14 items-center justify-center rounded-full border border-[#E5E7EB] bg-white text-primary">
              <Icon icon={isLoginMode ? 'lucide:user-check' : 'lucide:user-plus'} className="h-6 w-6" />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block">
              <div className="mb-2 text-sm font-semibold text-primary">用户名</div>
              <input
                value={form.username}
                onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="请输入 3-50 位用户名"
                className="w-full rounded-[1.5rem] border border-[#D6D6D6] bg-white px-4 py-4 text-sm text-primary outline-none transition-colors placeholder:text-text-muted focus:border-primary"
                required
              />
            </label>

            <label className="block">
              <div className="mb-2 text-sm font-semibold text-primary">密码</div>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                placeholder="请输入不少于 6 位的密码"
                className="w-full rounded-[1.5rem] border border-[#D6D6D6] bg-white px-4 py-4 text-sm text-primary outline-none transition-colors placeholder:text-text-muted focus:border-primary"
                required
              />
            </label>

            {error ? (
              <div className="rounded-[1.4rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
            ) : null}

            {success ? (
              <div className="rounded-[1.4rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                {success}
              </div>
            ) : null}

            <button type="submit" disabled={submitting} className="dream-button-primary w-full py-4 disabled:opacity-70">
              {submitting ? '处理中...' : isLoginMode ? '立即登录' : '提交注册'}
            </button>
          </form>

          <div className="mt-6 flex flex-col gap-4 rounded-[1.8rem] border border-[#EAEAEA] bg-white p-5 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-sm font-semibold text-primary">{isLoginMode ? '还没有账号？' : '已经拥有账号？'}</div>
              <div className="mt-1 text-sm text-text-muted">切换模式后即可继续使用同一个 Dreamstore 账户入口。</div>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsLoginMode((current) => !current);
                setError('');
                setSuccess('');
              }}
              className="dream-button-secondary"
            >
              {isLoginMode ? '去注册' : '去登录'}
            </button>
          </div>

          <div className="mt-5 flex items-center justify-between text-sm text-text-muted">
            <Link to="/" className="inline-flex items-center gap-2 hover:text-primary">
              <Icon icon="lucide:arrow-left" className="h-4 w-4" />
              返回首页
            </Link>
            <span>欢迎来到 Dreamstore</span>
          </div>
        </section>
      </div>
    </section>
  );
}
