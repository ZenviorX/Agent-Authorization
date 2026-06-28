import { useEffect, useMemo, useState } from 'react';
import { Icon } from './components/Icon';
import { GatewayWorkbench } from './pages/GatewayWorkbench';
import { Dashboard } from './pages/Dashboard';
import { RequestsPage } from './pages/RequestsPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { AuditPage } from './pages/AuditPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { ResearchComparisonPage } from './pages/ResearchComparisonPage';
import { TwoPhaseAuthorizationPage } from './pages/TwoPhaseAuthorizationPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';
import type {
  AuditLog,
  EvaluationMetric,
  GatewayRequest,
  Overview,
  PolicyRule,
  StrategyComparisonResponse,
  SystemSetting
} from './types/domain';
import './styles/global.css';
import './styles/layout.css';

const navItems = [
  { key: 'workbench', label: '授权工作台', icon: 'shield' },
  { key: 'dashboard', label: '总览仪表盘', icon: 'dashboard' },
  { key: 'requests', label: '授权请求', icon: 'requests' },
  { key: 'policies', label: '策略管理', icon: 'policies' },
  { key: 'audit', label: '审计日志', icon: 'audit' },
  { key: 'evaluation', label: '评测对比', icon: 'lab' },
  { key: 'research', label: '科研对比', icon: 'lab' },
  { key: 'twoPhase', label: '两阶段授权', icon: 'shield' },
  { key: 'settings', label: '系统设置', icon: 'settings' }
] as const;

type PageKey = typeof navItems[number]['key'];

export default function App() {
  const [page, setPage] = useState<PageKey>('workbench');
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [requests, setRequests] = useState<GatewayRequest[]>([]);
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationMetric[]>([]);
  const [strategyComparison, setStrategyComparison] = useState<StrategyComparisonResponse | null>(null);
  const [settings, setSettings] = useState<SystemSetting[]>([]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      const [
        overviewData,
        requestData,
        policyData,
        auditData,
        evaluationData,
        strategyComparisonData,
        settingData
      ] = await Promise.all([
        api.getOverview(),
        api.getRequests(),
        api.getPolicies(),
        api.getAuditLogs(),
        api.getEvaluations(),
        api.getStrategyComparison(),
        api.getSettings()
      ]);
      if (!mounted) return;
      setOverview(overviewData);
      setRequests(requestData);
      setPolicies(policyData);
      setAuditLogs(auditData);
      setEvaluations(evaluationData);
      setStrategyComparison(strategyComparisonData);
      setSettings(settingData);
      setLoading(false);
    }
    void load();
    return () => { mounted = false; };
  }, []);

  const currentTitle = useMemo(() => navItems.find((item) => item.key === page)?.label ?? '页面', [page]);

  async function handleDecision(id: string, result: 'approved' | 'rejected') {
    await api.submitDecision(id, result);
    setRequests((old) => old.map((item) => item.id === id ? {
      ...item,
      status: result,
      decision: result === 'approved' ? 'allow' : 'deny',
      reason: result === 'approved' ? `${item.reason}（已人工批准）` : `${item.reason}（已人工拒绝）`
    } : item));
  }

  const content = {
    workbench: <GatewayWorkbench />,
    dashboard: <Dashboard overview={overview} requests={requests} auditLogs={auditLogs} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    requests: <RequestsPage requests={requests} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    policies: <PoliciesPage policies={policies} />,
    audit: <AuditPage logs={auditLogs} />,
    evaluation: <EvaluationPage metrics={evaluations} strategyComparison={strategyComparison} />,
    research: <ResearchComparisonPage />,
    twoPhase: <TwoPhaseAuthorizationPage />,
    settings: <SettingsPage settings={settings} />
  }[page];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="shield" /></div>
          <div>
            <strong>ZenviorX</strong>
            <span>AI Agent 授权</span>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={page === item.key ? 'active' : ''}
              onClick={() => setPage(item.key)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <span>System Status</span>
          <strong>{loading ? 'Loading...' : 'Protected'}</strong>
          <small>Command ? Agent ? Gateway ? {overview?.activePolicies ?? 0} policies</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">AgentGuard</span>
            <h1>{currentTitle}</h1>
          </div>
          <div className="topbar-actions">
            <div className="search-box">搜索 / 请求 / 策略</div>
            <button className="primary-btn small" onClick={() => setPage('workbench')}>新建授权</button>
          </div>
        </header>

        {loading ? (
          <div className="loading-screen">
            <div className="loader" />
            <p>正在加载安全网关数据...</p>
          </div>
        ) : content}
      </main>
    </div>
  );
}
