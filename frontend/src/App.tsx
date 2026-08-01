import { useEffect, useMemo, useState } from 'react';
import { LiveStatus } from './components/LiveStatus';
import { useLiveRuntime } from './hooks/useLiveRuntime';
import { AuthenticationPage } from './pages/AuthenticationPage';
import { Dashboard } from './pages/Dashboard';
import { EvaluationPage } from './pages/EvaluationPage';
import { GatewayWorkbench } from './pages/GatewayWorkbench';
import { ResearchComparisonPage } from './pages/ResearchComparisonPage';
import { SecurityOverview } from './pages/SecurityOverview';
import { api } from './services/api';
import type { StrategyComparisonResponse } from './types/domain';
import './styles/global.css';
import './styles/layout.css';
import './styles/realtime-console.css';
import './styles/overview-hero-header.css';
import './styles/sidebar-authentication.css';

type PageKey = 'auth' | 'overview' | 'workbench' | 'evidence' | 'test' | 'research';

const navItems: Array<{
  key: PageKey;
  label: string;
  subtitle: string;
}> = [
  { key: 'auth', label: 'MCP / OAuth 认证', subtitle: '认证服务与协议状态' },
  { key: 'overview', label: '安全总览', subtitle: '实时状态与安全链路' },
  { key: 'workbench', label: '实时演示', subtitle: '发起任务并观察决策' },
  { key: 'evidence', label: '审计证据', subtitle: '运行记录与事件时间线' },
  { key: 'test', label: '评测对比', subtitle: '测试指标与策略图表' },
  { key: 'research', label: '研究说明', subtitle: '方法定位与实验逻辑' }
];

export default function App() {
  const [page, setPage] = useState<PageKey>('auth');
  const [strategyComparison, setStrategyComparison] = useState<StrategyComparisonResponse | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [testRunMessage, setTestRunMessage] = useState<string | null>(null);
  const { snapshot, connectionState, error, refresh } = useLiveRuntime();

  const currentNavItem = useMemo(
    () => navItems.find((item) => item.key === page),
    [page]
  );

  useEffect(() => {
    let active = true;
    api.getStrategyComparison().then((result) => {
      if (active) setStrategyComparison(result);
    });
    return () => { active = false; };
  }, []);

  async function handleRunIndependentTests() {
    setTestRunning(true);
    setTestRunMessage('正在运行独立 Gateway 测试，请稍候…');
    try {
      const result = await api.runIndependentTests();
      setTestRunMessage(
        result.success
          ? `测试完成：${result.summary.passed_cases}/${result.summary.total_cases} 通过。`
          : `测试执行失败：退出码 ${result.returncode}。`
      );
      window.dispatchEvent(new Event('agentguard:runtime-changed'));
      await refresh();
    } catch (reason) {
      setTestRunMessage(reason instanceof Error ? reason.message : '测试执行失败。');
    } finally {
      setTestRunning(false);
    }
  }

  const content: Record<PageKey, JSX.Element> = {
    auth: (
      <AuthenticationPage
        snapshot={snapshot}
        connectionState={connectionState}
      />
    ),
    overview: (
      <SecurityOverview
        snapshot={snapshot}
        connectionState={connectionState}
        onNavigate={(target) => setPage(target)}
      />
    ),
    workbench: <GatewayWorkbench />,
    evidence: (
      <Dashboard
        overview={snapshot?.overview ?? null}
        requests={snapshot?.requests ?? []}
        auditLogs={snapshot?.auditLogs ?? []}
        connectionState={connectionState}
        lastUpdated={snapshot?.generatedAt ?? null}
      />
    ),
    test: (
      <EvaluationPage
        metrics={snapshot?.evaluations ?? []}
        strategyComparison={strategyComparison}
        testSummary={snapshot?.testSummary ?? null}
        testRunning={testRunning}
        testRunMessage={testRunMessage}
        onRunTests={() => void handleRunIndependentTests()}
        onRefreshTestSummary={() => void refresh()}
      />
    ),
    research: <ResearchComparisonPage />
  };

  return (
    <div className="app-shell clean-shell realtime-shell">
      <aside className="sidebar clean-sidebar realtime-sidebar">
        <div className="brand clean-brand realtime-brand">
          <strong>AgentGuard</strong>
          <span>MCP Agent Security Console</span>
        </div>

        <nav className="nav-list clean-nav realtime-nav" aria-label="AgentGuard frontend navigation">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={page === item.key ? 'active' : ''}
              onClick={() => setPage(item.key)}
            >
              <span className="nav-copy">
                <strong>{item.label}</strong>
                <small>{item.subtitle}</small>
              </span>
            </button>
          ))}
        </nav>

        <div className="sidebar-spacer" />

        <section
          className={`sidebar-security-status status-${connectionState}`}
          aria-label="系统状态与安全主线"
        >
          <div className="sidebar-status-row">
            <div className="sidebar-status-name">
              <span className="sidebar-status-dot" />
              <span>系统状态</span>
            </div>
            <strong className="sidebar-status-value">{connectionState.toUpperCase()}</strong>
          </div>
          <small className="sidebar-status-detail">
            {snapshot?.systemStatus.execution_entrypoint ?? '等待后端状态'}
          </small>

          <div className="sidebar-status-divider" />

          <span className="sidebar-security-label">安全主线</span>
          <div className="sidebar-security-flow">
            OAuth → MCP → Task Boundary → Token → Sandbox → Evidence
          </div>
          <p className="sidebar-security-note">
            页面每 2 秒读取本机后端状态；窗口重新聚焦时立即刷新。
          </p>
        </section>
      </aside>

      <main className="main-panel clean-main realtime-main">
        <header className={`topbar clean-topbar realtime-topbar ${page === 'overview' ? 'overview-actions-only' : ''}`}>
          {page !== 'overview' && (
            <div>
              <span className="eyebrow">AgentGuard Security Operations</span>
              <h1>{currentNavItem?.label ?? 'MCP / OAuth 认证'}</h1>
              <p className="topbar-desc">{currentNavItem?.subtitle ?? '认证服务与协议状态。'}</p>
            </div>
          )}
          <div className="topbar-actions realtime-topbar-actions">
            <button className="secondary-btn small" onClick={() => void refresh()}>立即刷新</button>
            <LiveStatus state={connectionState} snapshot={snapshot} error={error} />
          </div>
        </header>

        {error && connectionState !== 'offline' && (
          <div className="runtime-warning">
            <strong>部分数据源暂不可用</strong>
            <span>{error.split('\n')[0]}</span>
          </div>
        )}

        {connectionState === 'offline' && !snapshot ? (
          <div className="offline-screen">
            <div className="offline-icon">!</div>
            <h2>无法连接 AgentGuard 后端</h2>
            <p>请确认 FastAPI 已运行在 127.0.0.1:8000。页面会继续自动重试，也可以点击“立即刷新”。</p>
            <button className="primary-btn" onClick={() => void refresh()}>重新连接</button>
          </div>
        ) : content[page]}
      </main>
    </div>
  );
}
