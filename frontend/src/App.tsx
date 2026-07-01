import { useEffect, useMemo, useState } from 'react';
import { Icon } from './components/Icon';
import { GatewayWorkbench } from './pages/GatewayWorkbench';
import { Dashboard } from './pages/Dashboard';
import { EvaluationPage } from './pages/EvaluationPage';
import { ResearchComparisonPage } from './pages/ResearchComparisonPage';
import { api } from './services/api';
import type {
  AuditLog,
  EvaluationMetric,
  GatewayRequest,
  Overview,
  StrategyComparisonResponse,
  TestResultSummary
} from './types/domain';
import './styles/global.css';
import './styles/layout.css';

type PageKey = 'workbench' | 'evidence' | 'test' | 'about';

const navItems: Array<{
  key: PageKey;
  label: string;
  subtitle: string;
  icon: string;
}> = [
  { key: 'workbench', label: '授权演示', subtitle: '输入任务并查看授权结果', icon: 'shield' },
  { key: 'evidence', label: '运行证据', subtitle: '读取本地运行记录', icon: 'dashboard' },
  { key: 'test', label: '测试报告', subtitle: '一键运行 Gateway 测试', icon: 'lab' },
  { key: 'about', label: '项目说明', subtitle: '理解项目定位和对比逻辑', icon: 'spark' }
];

export default function App() {
  const [page, setPage] = useState<PageKey>('workbench');
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [requests, setRequests] = useState<GatewayRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationMetric[]>([]);
  const [strategyComparison, setStrategyComparison] = useState<StrategyComparisonResponse | null>(null);
  const [testSummary, setTestSummary] = useState<TestResultSummary | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [testRunMessage, setTestRunMessage] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState('-');

  const currentNavItem = useMemo(() => navItems.find((item) => item.key === page), [page]);

  async function refreshRuntimeData() {
    const [overviewData, requestData, auditData, evaluationData] = await Promise.all([
      api.getOverview(),
      api.getRequests(),
      api.getAuditLogs(),
      api.getEvaluations()
    ]);
    setOverview(overviewData);
    setRequests(requestData);
    setAuditLogs(auditData);
    setEvaluations(evaluationData);
    setLastRefresh(new Date().toLocaleTimeString());
  }

  async function refreshTestSummary() {
    const summary = await api.getTestResultSummary();
    setTestSummary(summary);
    return summary;
  }

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      const [strategyComparisonData, testSummaryData] = await Promise.all([
        api.getStrategyComparison(),
        api.getTestResultSummary()
      ]);
      if (!mounted) return;
      setStrategyComparison(strategyComparisonData);
      setTestSummary(testSummaryData);
      await refreshRuntimeData();
      if (!mounted) return;
      setLoading(false);
    }

    void load();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (page === 'evidence') {
      void refreshRuntimeData();
    }
  }, [page]);

  async function handleDecision(id: string, result: 'approved' | 'rejected') {
    await api.submitDecision(id, result);
    await refreshRuntimeData();
  }

  async function handleRunIndependentTests() {
    setTestRunning(true);
    setTestRunMessage('正在运行独立测试模块，请稍候...');
    try {
      const result = await api.runIndependentTests();
      setTestSummary(result.summary);
      setTestRunMessage(result.success ? `测试完成：${result.summary.passed_cases}/${result.summary.total_cases} 通过。` : `测试执行失败：退出码 ${result.returncode}。`);
      await refreshRuntimeData();
    } catch (error) {
      setTestRunMessage(error instanceof Error ? error.message : '测试执行失败。');
      await refreshTestSummary();
      await refreshRuntimeData();
    } finally {
      setTestRunning(false);
    }
  }

  const content = {
    workbench: <GatewayWorkbench />,
    evidence: <Dashboard overview={overview} requests={requests} auditLogs={auditLogs} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    test: (
      <EvaluationPage
        metrics={evaluations}
        strategyComparison={strategyComparison}
        testSummary={testSummary}
        testRunning={testRunning}
        testRunMessage={testRunMessage}
        onRunTests={() => void handleRunIndependentTests()}
        onRefreshTestSummary={() => void refreshTestSummary()}
      />
    ),
    about: <ResearchComparisonPage />
  }[page];

  return (
    <div className="app-shell clean-shell">
      <aside className="sidebar clean-sidebar">
        <div className="brand clean-brand">
          <div className="brand-mark"><Icon name="shield" /></div>
          <div>
            <strong>AgentGuard</strong>
            <span>智能体授权网关</span>
          </div>
        </div>
        <nav className="nav-list clean-nav" aria-label="AgentGuard frontend navigation">
          {navItems.map((item, index) => (
            <button key={item.key} className={page === item.key ? 'active' : ''} onClick={() => setPage(item.key)}>
              <Icon name={item.icon} />
              <span><strong>{index + 1}. {item.label}</strong><small>{item.subtitle}</small></span>
            </button>
          ))}
        </nav>
        <div className="sidebar-card clean-sidebar-card">
          <span>主线</span>
          <strong>Agent → Gateway → Sandbox</strong>
          <small>先演示授权，再查看证据，最后运行测试。</small>
        </div>
      </aside>
      <main className="main-panel clean-main">
        <header className="topbar clean-topbar">
          <div>
            <span className="eyebrow">AgentGuard</span>
            <h1>{currentNavItem?.label ?? '授权演示'}</h1>
            <p className="topbar-desc">{currentNavItem?.subtitle ?? '智能体工具调用授权网关。'}{page === 'evidence' ? ` 上次刷新：${lastRefresh}` : ''}</p>
          </div>
          <div className="topbar-actions">
            {page === 'evidence' && <button className="secondary-btn small" onClick={() => void refreshRuntimeData()}>刷新数据</button>}
            <button className="secondary-btn small" onClick={() => setPage('workbench')}>回到演示</button>
          </div>
        </header>
        {loading ? (
          <div className="loading-screen"><div className="loader" /><p>正在加载前端数据...</p></div>
        ) : content}
      </main>
    </div>
  );
}
